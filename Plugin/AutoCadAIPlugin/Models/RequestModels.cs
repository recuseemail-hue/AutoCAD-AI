using System.Text.Json.Serialization;

namespace AutoCadAIPlugin.Models;

public class CadPayload
{
    [JsonPropertyName("schema_version")] public string SchemaVersion { get; set; } = string.Empty;
    [JsonPropertyName("run_id")] public string? RunId { get; set; }
    [JsonPropertyName("import_id")] public string? ImportId { get; set; }
    [JsonPropertyName("command_id")] public string CommandId { get; set; } = string.Empty;
    [JsonPropertyName("submitted_at")] public string? SubmittedAt { get; set; }
    [JsonPropertyName("application")] public string Application { get; set; } = string.Empty;
    [JsonPropertyName("operation")] public string Operation { get; set; } = string.Empty;
    [JsonPropertyName("parameters")] public LineParams Parameters { get; set; } = new();
    [JsonPropertyName("units")] public string Units { get; set; } = string.Empty;
    [JsonPropertyName("coordinate_system")] public string CoordinateSystem { get; set; } = string.Empty;
    [JsonPropertyName("requires_approval")] public bool RequiresApproval { get; set; }
}

public class LineParams
{
    [JsonPropertyName("start")] public Point3D Start { get; set; } = new();
    [JsonPropertyName("end")] public Point3D End { get; set; } = new();
    [JsonPropertyName("layer")] public string Layer { get; set; } = "0";
    [JsonPropertyName("create_layer_if_missing")] public bool CreateLayerIfMissing { get; set; }
}

public class Point3D
{
    [JsonPropertyName("x")] public double X { get; set; }
    [JsonPropertyName("y")] public double Y { get; set; }
    [JsonPropertyName("z")] public double Z { get; set; }
}
