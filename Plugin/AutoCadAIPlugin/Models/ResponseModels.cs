using System.Text.Json.Serialization;

namespace AutoCadAIPlugin.Models;

public sealed class CadResponse
{
    public const string PluginVersion = "0.3.0";

    [JsonPropertyName("schema_version")]
    public string SchemaVersion { get; init; } = "0.1";

    [JsonPropertyName("run_id")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public string? RunId { get; init; }

    [JsonPropertyName("import_id")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public string? ImportId { get; init; }

    [JsonPropertyName("command_id")]
    public string CommandId { get; init; } = string.Empty;

    [JsonPropertyName("application")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public string? Application { get; init; }

    [JsonPropertyName("operation")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public string? Operation { get; init; }

    [JsonPropertyName("status")]
    public string Status { get; init; } = string.Empty;

    [JsonPropertyName("message")]
    public string Message { get; init; } = string.Empty;

    [JsonPropertyName("error")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public CadError? Error { get; init; }

    [JsonPropertyName("affected_objects")]
    public IReadOnlyList<AffectedObject> AffectedObjects { get; init; } = [];

    [JsonPropertyName("data")]
    public object? Data { get; init; }

    [JsonPropertyName("undo_token")]
    public string? UndoToken { get; init; }

    [JsonPropertyName("warnings")]
    public IReadOnlyList<string> Warnings { get; init; } = [];

    [JsonPropertyName("document")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public CadDocumentInfo? Document { get; init; }

    [JsonPropertyName("plugin_version")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public string? ReportedPluginVersion { get; init; }

    [JsonPropertyName("completed_at")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public string? CompletedAt { get; init; }

    public static CadResponse FromError(
        CadPayload payload,
        string code,
        string message,
        string? documentName = null,
        params string[] warnings)
    {
        bool isTraceable = payload.SchemaVersion is "0.2" or "0.3";
        return new CadResponse
        {
            SchemaVersion = payload.SchemaVersion,
            RunId = isTraceable ? payload.RunId : null,
            ImportId = isTraceable ? payload.ImportId : null,
            CommandId = payload.CommandId,
            Application = isTraceable ? payload.Application : null,
            Operation = isTraceable ? payload.Operation : null,
            Status = "error",
            Message = message,
            Error = isTraceable
                ? new CadError
                {
                    Code = code,
                    Message = message,
                    Details = null
                }
                : null,
            Document = isTraceable && !string.IsNullOrWhiteSpace(documentName)
                ? new CadDocumentInfo { Name = documentName }
                : null,
            ReportedPluginVersion = isTraceable ? PluginVersion : null,
            CompletedAt = isTraceable
                ? DateTimeOffset.UtcNow.ToString("O")
                : null,
            Warnings = warnings
        };
    }

    public static CadResponse SystemError(
        string commandId,
        string code,
        string message,
        params string[] warnings) => new()
        {
            CommandId = commandId,
            Status = "error",
            Message = message,
            Error = new CadError
            {
                Code = code,
                Message = message,
                Details = null
            },
            ReportedPluginVersion = PluginVersion,
            CompletedAt = DateTimeOffset.UtcNow.ToString("O"),
            Warnings = warnings
        };
}

public sealed class CadError
{
    [JsonPropertyName("code")]
    public string Code { get; init; } = string.Empty;

    [JsonPropertyName("message")]
    public string Message { get; init; } = string.Empty;

    [JsonPropertyName("details")]
    public object? Details { get; init; }
}

public sealed class CadDocumentInfo
{
    [JsonPropertyName("name")]
    public string Name { get; init; } = string.Empty;
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
