using System;
using System.IO;
using System.Net;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;
using AutoCadAIPlugin.Models;

namespace AutoCadAIPlugin.Services;

public class PythonBridge
{
    private HttpListener? _listener;
    private readonly DrawingService _drawingService = new();
    private bool _isRunning;

    public void Start(int port = 8080)
    {
        if (_isRunning) return;

        _listener = new HttpListener();
        _listener.Prefixes.Add($"http://localhost:{port}/command/");
        _listener.Start();
        _isRunning = true;

        // Run the listener loop on a background thread so it doesn't freeze the AutoCAD UI
        Task.Run(() => ListenLoopAsync());
    }

    public void Stop()
    {
        _isRunning = false;
        _listener?.Stop();
        _listener?.Close();
    }

    private async Task ListenLoopAsync()
    {
        while (_isRunning && _listener != null)
        {
            try
            {
                HttpListenerContext context = await _listener.GetContextAsync();
                _ = Task.Run(() => ProcessRequestAsync(context)); // Handle request concurrently
            }
            catch (HttpListenerException) when (!_isRunning)
            {
                // Expected exception when stopping the listener
            }
            catch (Exception ex)
            {
                // In production, log this error to your AutoCAD console or file logger
                Console.WriteLine($"Bridge error: {ex.Message}");
            }
        }
    }

    private async Task ProcessRequestAsync(HttpListenerContext context)
    {
        HttpListenerRequest request = context.Request;
        HttpListenerResponse response = context.Response;

        if (request.HttpMethod == "POST")
        {
            try
            {
                // 1. Read raw JSON string from Python payload stream
                using StreamReader reader = new(request.InputStream, Encoding.UTF8);
                string jsonString = await reader.ReadToEndAsync();

                // 2. Parse using the .NET 10 serialization model
                CadPayload? payload = JsonSerializer.Deserialize<CadPayload>(jsonString);

                if (payload != null && payload.Operation.Equals("create_line", StringComparison.OrdinalIgnoreCase))
                {
                    // 3. Dispatch to your drawing service execution layout
                    // Note: AutoCAD transactions must run on the primary document execution context thread. 
                    // This service class invocation logic handles drawing routing.
                    _drawingService.CreateLine(payload);

                    // 4. Return structural mock success response back to Python
                    var successObj = new { status = "success", command_id = payload.CommandId, message = "Line created." };
                    byte[] buffer = Encoding.UTF8.GetBytes(JsonSerializer.Serialize(successObj));

                    response.StatusCode = (int)HttpStatusCode.OK;
                    response.ContentType = "application/json";
                    response.ContentLength64 = buffer.Length;
                    await response.OutputStream.WriteAsync(buffer);
                }
                else
                {
                    await SendErrorResponse(response, HttpStatusCode.BadRequest, "Unsupported operation payload target.");
                }
            }
            catch (Exception ex)
            {
                await SendErrorResponse(response, HttpStatusCode.InternalServerError, ex.Message);
            }
        }
        else
        {
            await SendErrorResponse(response, HttpStatusCode.MethodNotAllowed, "Only POST is allowed.");
        }

        response.Close();
    }

    private async Task SendErrorResponse(HttpListenerResponse response, HttpStatusCode status, string message)
    {
        var errorObj = new { status = "error", message = message };
        byte[] buffer = Encoding.UTF8.GetBytes(JsonSerializer.Serialize(errorObj));
        response.StatusCode = (int)status;
        response.ContentType = "application/json";
        response.ContentLength64 = buffer.Length;
        await response.OutputStream.WriteAsync(buffer);
    }
}
