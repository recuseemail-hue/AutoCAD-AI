using Autodesk.AutoCAD.Runtime;
using AutoCadAIPlugin.Services;

[assembly: ExtensionApplication(typeof(AutoCadAIPlugin.Initialization))]

namespace AutoCadAIPlugin;

public class Initialization : IExtensionApplication
{
    private readonly PythonBridge _bridge = new();

    public void Initialize()
    {
        // Automatically open port 8080 on plugin startup
        _bridge.Start(8080);
    }

    public void Terminate()
    {
        // Ensure the port shuts down safely when AutoCAD exits
        _bridge.Stop();
    }
}
