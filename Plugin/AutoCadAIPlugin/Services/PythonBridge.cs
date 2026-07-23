using System.Collections.Concurrent;
using System.Net;
using System.Text;
using System.Text.Json;
using AutoCadAIPlugin.Models;
using Autodesk.AutoCAD.ApplicationServices;
using Application = Autodesk.AutoCAD.ApplicationServices.Application;

namespace AutoCadAIPlugin.Services;

public sealed class PythonBridge
{
    public const int DefaultPort = 8765;

    private const int MaxRequestBytes = 1024 * 1024;
    private static readonly TimeSpan CommandTimeout = TimeSpan.FromSeconds(30);
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true,
        WriteIndented = true
    };

    private readonly ConcurrentQueue<PendingCommand> _pendingCommands = new();
    private readonly DrawingService _drawingService = new();
    private HttpListener? _listener;
    private CancellationTokenSource? _shutdown;

    public bool IsRunning { get; private set; }

    public int Port { get; private set; }

    public string Endpoint => $"http://localhost:{Port}/command";

    public void Start(int port = DefaultPort)
    {
        if (IsRunning)
        {
            return;
        }

        HttpListener listener = new();
        listener.Prefixes.Add($"http://localhost:{port}/");

        try
        {
            listener.Start();
        }
        catch
        {
            listener.Close();
            throw;
        }

        _listener = listener;
        _shutdown = new CancellationTokenSource();
        Port = port;
        IsRunning = true;

        // AutoCAD database work is drained on its UI thread from the Idle event.
        Application.Idle += OnApplicationIdle;
        _ = Task.Run(() => ListenLoopAsync(listener, _shutdown.Token));
    }

    public void Stop()
    {
        if (!IsRunning)
        {
            return;
        }

        IsRunning = false;
        Application.Idle -= OnApplicationIdle;
        _shutdown?.Cancel();
        _listener?.Close();
        _listener = null;

        while (_pendingCommands.TryDequeue(out PendingCommand? pending))
        {
            pending.Completion.TrySetCanceled();
        }

        _shutdown?.Dispose();
        _shutdown = null;
    }

    private async Task ListenLoopAsync(HttpListener listener, CancellationToken cancellationToken)
    {
        while (!cancellationToken.IsCancellationRequested && listener.IsListening)
        {
            try
            {
                HttpListenerContext context = await listener.GetContextAsync()
                    .WaitAsync(cancellationToken);
                _ = ProcessRequestSafelyAsync(context, cancellationToken);
            }
            catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
            {
                break;
            }
            catch (HttpListenerException) when (!listener.IsListening)
            {
                break;
            }
            catch (ObjectDisposedException)
            {
                break;
            }
        }
    }

    private async Task ProcessRequestSafelyAsync(
        HttpListenerContext context,
        CancellationToken cancellationToken)
    {
        try
        {
            await ProcessRequestAsync(context, cancellationToken);
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            // AutoCAD is shutting down; the client connection may already be gone.
        }
        catch (Exception exception)
        {
            await TryWriteJsonAsync(
                context.Response,
                CadResponse.SystemError(
                    string.Empty,
                    "PLUGIN_BRIDGE_ERROR",
                    $"Bridge error: {exception.Message}"),
                HttpStatusCode.InternalServerError,
                CancellationToken.None);
        }
        finally
        {
            context.Response.Close();
        }
    }

    private async Task ProcessRequestAsync(
        HttpListenerContext context,
        CancellationToken cancellationToken)
    {
        HttpListenerRequest request = context.Request;
        HttpListenerResponse response = context.Response;
        string path = request.Url?.AbsolutePath.TrimEnd('/') ?? string.Empty;

        if (string.Equals(path, "/health", StringComparison.OrdinalIgnoreCase))
        {
            if (!string.Equals(request.HttpMethod, "GET", StringComparison.OrdinalIgnoreCase))
            {
                response.Headers["Allow"] = "GET";
                await WriteJsonAsync(
                    response,
                    CadResponse.SystemError(
                        string.Empty,
                        "METHOD_NOT_ALLOWED",
                        "Only GET is allowed for /health."),
                    HttpStatusCode.MethodNotAllowed,
                    cancellationToken);
                return;
            }

            await WriteJsonAsync(
                response,
                new
                {
                    status = "ok",
                    application = "autocad",
                    plugin_version = CadResponse.PluginVersion,
                    supported_schema_versions = new[] { "0.1", "0.2" }
                },
                HttpStatusCode.OK,
                cancellationToken);
            return;
        }

        if (!string.Equals(path, "/command", StringComparison.OrdinalIgnoreCase))
        {
            await WriteJsonAsync(
                response,
                CadResponse.SystemError(
                    string.Empty,
                    "ROUTE_NOT_FOUND",
                    "Route not found. Use POST /command or GET /health."),
                HttpStatusCode.NotFound,
                cancellationToken);
            return;
        }

        if (!string.Equals(request.HttpMethod, "POST", StringComparison.OrdinalIgnoreCase))
        {
            response.Headers["Allow"] = "POST";
            await WriteJsonAsync(
                response,
                CadResponse.SystemError(
                    string.Empty,
                    "METHOD_NOT_ALLOWED",
                    "Only POST is allowed for /command."),
                HttpStatusCode.MethodNotAllowed,
                cancellationToken);
            return;
        }

        if (request.ContentLength64 > MaxRequestBytes)
        {
            await WriteJsonAsync(
                response,
                CadResponse.SystemError(
                    string.Empty,
                    "REQUEST_TOO_LARGE",
                    "The JSON request exceeds the 1 MB limit."),
                HttpStatusCode.RequestEntityTooLarge,
                cancellationToken);
            return;
        }

        CadPayload? payload;
        try
        {
            using StreamReader reader = new(
                request.InputStream,
                request.ContentEncoding ?? Encoding.UTF8,
                detectEncodingFromByteOrderMarks: true,
                leaveOpen: true);
            string json = await reader.ReadToEndAsync(cancellationToken);
            payload = JsonSerializer.Deserialize<CadPayload>(json, JsonOptions);
        }
        catch (JsonException exception)
        {
            await WriteJsonAsync(
                response,
                CadResponse.SystemError(
                    string.Empty,
                    "MALFORMED_JSON",
                    $"Malformed JSON: {exception.Message}"),
                HttpStatusCode.BadRequest,
                cancellationToken);
            return;
        }

        if (payload == null)
        {
            await WriteJsonAsync(
                response,
                CadResponse.SystemError(
                    string.Empty,
                    "REQUEST_BODY_REQUIRED",
                    "The JSON request body is required."),
                HttpStatusCode.BadRequest,
                cancellationToken);
            return;
        }

        PendingCommand pending = new(payload);
        _pendingCommands.Enqueue(pending);

        try
        {
            CadResponse commandResponse = await pending.Completion.Task
                .WaitAsync(CommandTimeout, cancellationToken);
            await WriteJsonAsync(response, commandResponse, HttpStatusCode.OK, cancellationToken);
        }
        catch (TimeoutException)
        {
            pending.Completion.TrySetCanceled();
            await WriteJsonAsync(
                response,
                CadResponse.FromError(
                    payload,
                    "AUTOCAD_IDLE_TIMEOUT",
                    "AutoCAD did not become idle within 30 seconds; the command was not executed."),
                HttpStatusCode.ServiceUnavailable,
                cancellationToken);
        }
        catch (CadRequestException exception)
        {
            await WriteJsonAsync(
                response,
                CadResponse.FromError(
                    payload,
                    exception.Code,
                    exception.Message,
                    GetActiveDocumentName()),
                HttpStatusCode.BadRequest,
                cancellationToken);
        }
        catch (Exception exception)
        {
            await WriteJsonAsync(
                response,
                CadResponse.FromError(
                    payload,
                    "AUTOCAD_EXECUTION_ERROR",
                    $"AutoCAD command failed: {exception.Message}",
                    GetActiveDocumentName()),
                HttpStatusCode.InternalServerError,
                cancellationToken);
        }
    }

    private void OnApplicationIdle(object? sender, EventArgs eventArgs)
    {
        const int maxCommandsPerIdleCycle = 20;

        for (int index = 0;
             index < maxCommandsPerIdleCycle && _pendingCommands.TryDequeue(out PendingCommand? pending);
             index++)
        {
            if (pending.Completion.Task.IsCompleted)
            {
                continue;
            }

            try
            {
                Document document = Application.DocumentManager.MdiActiveDocument;
                if (document == null)
                {
                    throw new CadRequestException(
                        "NO_ACTIVE_DOCUMENT",
                        "No active AutoCAD drawing is available.");
                }

                using DocumentLock documentLock = document.LockDocument();
                CadResponse response = _drawingService.CreateLine(pending.Payload);
                pending.Completion.TrySetResult(response);
            }
            catch (Exception exception)
            {
                pending.Completion.TrySetException(exception);
            }
        }
    }

    private static async Task WriteJsonAsync<T>(
        HttpListenerResponse response,
        T value,
        HttpStatusCode statusCode,
        CancellationToken cancellationToken)
    {
        byte[] buffer = JsonSerializer.SerializeToUtf8Bytes(value, JsonOptions);
        response.StatusCode = (int)statusCode;
        response.ContentType = "application/json; charset=utf-8";
        response.ContentEncoding = Encoding.UTF8;
        response.ContentLength64 = buffer.Length;
        await response.OutputStream.WriteAsync(buffer, cancellationToken);
    }

    private static string? GetActiveDocumentName()
    {
        Document? document = Application.DocumentManager.MdiActiveDocument;
        return document == null ? null : Path.GetFileName(document.Name);
    }

    private static async Task TryWriteJsonAsync<T>(
        HttpListenerResponse response,
        T value,
        HttpStatusCode statusCode,
        CancellationToken cancellationToken)
    {
        try
        {
            await WriteJsonAsync(response, value, statusCode, cancellationToken);
        }
        catch
        {
            // The client disconnected or the response had already started.
        }
    }

    private sealed class PendingCommand(CadPayload payload)
    {
        public CadPayload Payload { get; } = payload;

        public TaskCompletionSource<CadResponse> Completion { get; } =
            new(TaskCreationOptions.RunContinuationsAsynchronously);
    }
}
