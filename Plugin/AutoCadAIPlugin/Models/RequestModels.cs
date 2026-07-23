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
    [JsonPropertyName("parameters")] public CadParameters Parameters { get; set; } = new();
    [JsonPropertyName("units")] public string Units { get; set; } = string.Empty;
    [JsonPropertyName("coordinate_system")] public string CoordinateSystem { get; set; } = string.Empty;
    [JsonPropertyName("requires_approval")] public bool? RequiresApproval { get; set; }
}

public class CadParameters
{
    [JsonPropertyName("start")] public Point3D Start { get; set; } = new();
    [JsonPropertyName("end")] public Point3D End { get; set; } = new();
    [JsonPropertyName("layer")] public string Layer { get; set; } = "0";
    [JsonPropertyName("create_layer_if_missing")] public bool CreateLayerIfMissing { get; set; }
    [JsonPropertyName("window_min")] public Point3D? WindowMin { get; set; }
    [JsonPropertyName("window_max")] public Point3D? WindowMax { get; set; }
    [JsonPropertyName("object_id")] public string? ObjectId { get; set; }
    [JsonPropertyName("target_import_id")] public string? TargetImportId { get; set; }
    [JsonPropertyName("limit")] public int? Limit { get; set; }
    [JsonPropertyName("validate_only")] public bool? ValidateOnly { get; set; }
    [JsonPropertyName("expected_document")]
    public BatchExpectedDocument? ExpectedDocument { get; set; }
    [JsonPropertyName("entities")] public List<BatchEntity>? Entities { get; set; }
}

public class Point3D
{
    [JsonPropertyName("x")] public double X { get; set; }
    [JsonPropertyName("y")] public double Y { get; set; }
    [JsonPropertyName("z")] public double Z { get; set; }
}

public sealed class BatchExpectedDocument
{
    [JsonPropertyName("name")] public string? Name { get; set; }
    [JsonPropertyName("fingerprint_guid")] public string? FingerprintGuid { get; set; }
}

public sealed class BatchEntity
{
    [JsonPropertyName("client_entity_id")] public string? ClientEntityId { get; set; }
    [JsonPropertyName("entity_type")] public string? EntityType { get; set; }
    [JsonPropertyName("layer")] public string? Layer { get; set; }
    [JsonPropertyName("create_layer_if_missing")]
    public bool? CreateLayerIfMissing { get; set; }
    [JsonPropertyName("start")] public BatchPoint3D? Start { get; set; }
    [JsonPropertyName("end")] public BatchPoint3D? End { get; set; }
    [JsonPropertyName("vertices")] public List<BatchPoint3D>? Vertices { get; set; }
    [JsonPropertyName("closed")] public bool? Closed { get; set; }
}

public sealed class BatchPoint3D
{
    [JsonPropertyName("x")] public double? X { get; set; }
    [JsonPropertyName("y")] public double? Y { get; set; }
    [JsonPropertyName("z")] public double? Z { get; set; }
}
