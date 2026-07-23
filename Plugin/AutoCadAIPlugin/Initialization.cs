using AutoCadAIPlugin.Services;
using Autodesk.AutoCAD.Runtime;
using Application = Autodesk.AutoCAD.ApplicationServices.Application;

[assembly: ExtensionApplication(typeof(AutoCadAIPlugin.Initialization))]

namespace AutoCadAIPlugin;

public sealed class Initialization : IExtensionApplication
{
    public static PythonBridge Bridge { get; } = new();

    public void Initialize()
    {
        try
        {
            Bridge.Start();
            WriteMessage($"\nAutoCAD AI plugin loaded. Endpoint: {Bridge.Endpoint}");
        }
        catch (System.Exception exception)
        {
            WriteMessage(
                $"\nAutoCAD AI plugin loaded, but its HTTP endpoint could not start: {exception.Message}" +
                "\nRun AI_SERVER_START after resolving the port/URL reservation issue.");
        }
    }

    public void Terminate()
    {
        Bridge.Stop();
    }

    private static void WriteMessage(string message)
    {
        Application.DocumentManager.MdiActiveDocument?.Editor.WriteMessage(message);
    }
}
