using AutoCadAIPlugin.Models;
using AutoCadAIPlugin.Services;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.EditorInput;
using Autodesk.AutoCAD.Runtime;
using System.Reflection.Metadata;
using System.Text.Json;
using Application = Autodesk.AutoCAD.ApplicationServices.Application;

namespace AutoCadAIPlugin.Commands;

public class CadCommands
{
    private readonly DrawingService _drawingService = new();

    [CommandMethod("AI_DRAW_JSON")]
    public void AiDrawJson()
    {
        Autodesk.AutoCAD.ApplicationServices.Document doc = Application.DocumentManager.MdiActiveDocument;
        Editor ed = doc.Editor;

        PromptStringOptions opt = new("\nPaste JSON command payload: ") { AllowSpaces = true };
        PromptResult res = ed.GetString(opt);
        if (res.Status != PromptStatus.OK || string.IsNullOrWhiteSpace(res.StringResult)) return;

        try
        {
            // Parse native JSON using modern .NET 10 System.Text.Json engine
            CadPayload? payload = JsonSerializer.Deserialize<CadPayload>(res.StringResult);

            if (payload != null && payload.Operation.Equals("create_line", StringComparison.OrdinalIgnoreCase))
            {
                _drawingService.CreateLine(payload);
                ed.WriteMessage($"\n[Success] Command {payload.CommandId} processed successfully.");
            }
            else
            {
                ed.WriteMessage("\n[Error] Invalid operation type.");
            }
        }
        catch (JsonException jsonEx)
        {
            ed.WriteMessage($"\n[Error] Malformed JSON structure: {jsonEx.Message}");
        }
        catch (System.Exception ex)
        {
            ed.WriteMessage($"\n[Fatal Error] Engine exception: {ex.Message}");
        }
    }
}
