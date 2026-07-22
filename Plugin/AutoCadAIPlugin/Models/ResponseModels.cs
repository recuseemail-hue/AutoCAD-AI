using System.Text.Json.Serialization;

namespace AutoCadAIPlugin.Models;

public sealed class CadResponse
{
    [JsonPropertyName("schema_version")]
    public string SchemaVersion { get; init; } = "0.1";

    [JsonPropertyName("command_id")]
    public string CommandId { get; init; } = string.Empty;

    [JsonPropertyName("status")]
    public string Status { get; init; } = string.Empty;

    [JsonPropertyName("message")]
    public string Message { get; init; } = string.Empty;

    [JsonPropertyName("affected_objects")]
    public IReadOnlyList<AffectedObject> AffectedObjects { get; init; } = [];

    [JsonPropertyName("data")]
    public LineResponseData? Data { get; init; }

    [JsonPropertyName("undo_token")]
    public string? UndoToken { get; init; }

    [JsonPropertyName("warnings")]
    public IReadOnlyList<string> Warnings { get; init; } = [];

    public static CadResponse Error(string commandId, string message, params string[] warnings) => new()
    {
        CommandId = commandId,
        Status = "error",
        Message = message,
        Warnings = warnings
    };
}

public sealed class AffectedObject
{
    [JsonPropertyName("object_type")]
    public string ObjectType { get; init; } = string.Empty;

    [JsonPropertyName("object_id")]
    public string ObjectId { get; init; } = string.Empty;

    [JsonPropertyName("action")]
    public string Action { get; init; } = string.Empty;
}

public sealed class LineResponseData
{
    [JsonPropertyName("layer")]
    public string Layer { get; init; } = string.Empty;

    [JsonPropertyName("start_in_drawing_units")]
    public double[] StartInDrawingUnits { get; init; } = [];

    [JsonPropertyName("end_in_drawing_units")]
    public double[] EndInDrawingUnits { get; init; } = [];
}
