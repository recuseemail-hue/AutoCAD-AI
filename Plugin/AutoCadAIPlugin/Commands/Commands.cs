using System.Text.Json;
using AutoCadAIPlugin.Models;
using AutoCadAIPlugin.Services;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.EditorInput;
using Autodesk.AutoCAD.Runtime;
using Application = Autodesk.AutoCAD.ApplicationServices.Application;

[assembly: CommandClass(typeof(AutoCadAIPlugin.Commands.CadCommands))]

namespace AutoCadAIPlugin.Commands;

public sealed class CadCommands
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true,
        WriteIndented = true
    };

    private readonly DrawingService _drawingService = new();

    [CommandMethod("AI_DRAW_JSON")]
    public void AiDrawJson()
    {
        Document document = Application.DocumentManager.MdiActiveDocument;
        Editor editor = document.Editor;

        PromptStringOptions options = new("\nPaste a single-line JSON command payload: ")
        {
            AllowSpaces = true
        };
        PromptResult result = editor.GetString(options);
        if (result.Status != PromptStatus.OK || string.IsNullOrWhiteSpace(result.StringResult))
        {
            return;
        }

        try
        {
            CadPayload? payload = JsonSerializer.Deserialize<CadPayload>(
                result.StringResult,
                JsonOptions);
            if (payload == null)
            {
                throw new CadRequestException("The JSON request body is required.");
            }

            CadResponse response = _drawingService.CreateLine(payload);
            editor.WriteMessage($"\n{JsonSerializer.Serialize(response, JsonOptions)}");
        }
        catch (JsonException exception)
        {
            CadResponse response = CadResponse.SystemError(
                string.Empty,
                "MALFORMED_JSON",
                $"Malformed JSON: {exception.Message}");
            editor.WriteMessage($"\n{JsonSerializer.Serialize(response, JsonOptions)}");
        }
        catch (System.Exception exception)
        {
            CadResponse response = CadResponse.SystemError(
                string.Empty,
                "AUTOCAD_COMMAND_ERROR",
                exception.Message);
            editor.WriteMessage($"\n{JsonSerializer.Serialize(response, JsonOptions)}");
        }
    }

    [CommandMethod("AI_SERVER_START")]
    public void StartServer()
    {
        Editor editor = Application.DocumentManager.MdiActiveDocument.Editor;
        try
        {
            Initialization.Bridge.Start();
            editor.WriteMessage($"\nAutoCAD AI endpoint listening at {Initialization.Bridge.Endpoint}");
        }
        catch (System.Exception exception)
        {
            editor.WriteMessage($"\nUnable to start AutoCAD AI endpoint: {exception.Message}");
        }
    }

    [CommandMethod("AI_SERVER_STOP")]
    public void StopServer()
    {
        Initialization.Bridge.Stop();
        Application.DocumentManager.MdiActiveDocument.Editor.WriteMessage(
            "\nAutoCAD AI endpoint stopped.");
    }

    [CommandMethod("AI_SERVER_STATUS")]
    public void ServerStatus()
    {
        string status = Initialization.Bridge.IsRunning
            ? $"running at {Initialization.Bridge.Endpoint}"
            : "stopped";
        Application.DocumentManager.MdiActiveDocument.Editor.WriteMessage(
            $"\nAutoCAD AI endpoint is {status}.");
    }
}
