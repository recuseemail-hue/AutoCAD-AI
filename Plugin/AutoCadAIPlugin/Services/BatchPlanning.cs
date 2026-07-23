using AutoCadAIPlugin.Models;

namespace AutoCadAIPlugin.Services;

public sealed record BatchPlanPoint(double X, double Y, double Z);

public sealed record PlannedBatchEntity(
    string ClientEntityId,
    string EntityType,
    string Layer,
    bool CreateLayerIfMissing,
    BatchPlanPoint? Start,
    BatchPlanPoint? End,
    IReadOnlyList<BatchPlanPoint>? Vertices,
    bool Closed);

public sealed record BatchPlan(
    string RunId,
    string ImportId,
    string CommandId,
    bool ValidateOnly,
    string ExpectedDocumentName,
    Guid? ExpectedFingerprintGuid,
    string Units,
    IReadOnlyList<PlannedBatchEntity> Entities,
    int TotalPointCount);

public sealed record PlannedLayerAction(string Layer, string Action);

public sealed class BatchContractException : Exception
{
    public BatchContractException(
        string code,
        string message,
        IReadOnlyDictionary<string, object?>? details = null)
        : base(message)
    {
        Code = code;
        Details = details;
    }

    public string Code { get; }

    public IReadOnlyDictionary<string, object?>? Details { get; }
}

public static class BatchPlanner
{
    public const int MaximumEntities = 500;
    public const int MaximumPoints = 50_000;

    private static readonly HashSet<string> SupportedUnits =
    [
        "inches",
        "feet",
        "millimeters",
        "centimeters",
        "meters"
    ];

    public static BatchPlan Create(CadPayload payload)
    {
        ArgumentNullException.ThrowIfNull(payload);

        if (payload.SchemaVersion != "0.4")
        {
            throw InvalidCommand("execute_batch requires schema_version '0.4'.");
        }

        string runId = Required(payload.RunId, "run_id", 200);
        string importId = Required(payload.ImportId, "import_id", 200);
        string commandId = Required(payload.CommandId, "command_id", 200);
        if (string.IsNullOrWhiteSpace(payload.SubmittedAt) ||
            !DateTimeOffset.TryParse(payload.SubmittedAt, out _))
        {
            throw InvalidCommand("submitted_at must be a valid timestamp.");
        }

        if (payload.Application != "autocad")
        {
            throw InvalidCommand("application must be 'autocad'.");
        }

        if (payload.Operation != "execute_batch")
        {
            throw InvalidCommand("operation must be 'execute_batch'.");
        }

        if (payload.RequiresApproval is not false)
        {
            throw InvalidCommand("requires_approval must be false.");
        }

        if (payload.CoordinateSystem != "world")
        {
            throw InvalidCommand("coordinate_system must be 'world'.");
        }

        string units = Required(payload.Units, "units", 32).ToLowerInvariant();
        if (!SupportedUnits.Contains(units))
        {
            throw InvalidCommand(
                "units must be inches, feet, millimeters, centimeters, or meters.");
        }

        CadParameters parameters = payload.Parameters ??
            throw InvalidCommand("parameters is required.");
        if (!parameters.ValidateOnly.HasValue)
        {
            throw InvalidCommand("parameters.validate_only is required.");
        }

        BatchExpectedDocument expectedDocument =
            parameters.ExpectedDocument ??
            throw InvalidCommand("parameters.expected_document is required.");
        string expectedName = Required(
            expectedDocument.Name,
            "parameters.expected_document.name",
            260);
        Guid? expectedFingerprint = null;
        if (expectedDocument.FingerprintGuid != null)
        {
            if (!Guid.TryParseExact(
                    expectedDocument.FingerprintGuid,
                    "D",
                    out Guid parsedFingerprint))
            {
                throw InvalidCommand(
                    "parameters.expected_document.fingerprint_guid must be a GUID.");
            }

            expectedFingerprint = parsedFingerprint;
        }

        List<BatchEntity> entities = parameters.Entities ??
            throw LimitError("parameters.entities must contain 1 to 500 entities.");
        if (entities.Count is < 1 or > MaximumEntities)
        {
            throw LimitError("parameters.entities must contain 1 to 500 entities.");
        }

        HashSet<string> clientEntityIds = new(StringComparer.Ordinal);
        List<PlannedBatchEntity> plannedEntities = new(entities.Count);
        int totalPointCount = 0;
        for (int index = 0; index < entities.Count; index++)
        {
            BatchEntity entity = entities[index] ??
                throw InvalidGeometry($"Entity {index} is null.");
            PlannedBatchEntity planned = PlanEntity(entity, index);
            if (!clientEntityIds.Add(planned.ClientEntityId))
            {
                throw InvalidGeometry(
                    $"Duplicate client_entity_id '{planned.ClientEntityId}'.");
            }

            totalPointCount = checked(
                totalPointCount +
                (planned.EntityType == "line" ? 2 : planned.Vertices!.Count));
            if (totalPointCount > MaximumPoints)
            {
                throw LimitError(
                    $"Batch contains more than {MaximumPoints} total points.");
            }

            plannedEntities.Add(planned);
        }

        return new BatchPlan(
            runId,
            importId,
            commandId,
            parameters.ValidateOnly.Value,
            expectedName,
            expectedFingerprint,
            units,
            plannedEntities,
            totalPointCount);
    }

    private static PlannedBatchEntity PlanEntity(BatchEntity entity, int index)
    {
        string prefix = $"parameters.entities[{index}]";
        string clientEntityId = Required(
            entity.ClientEntityId,
            $"{prefix}.client_entity_id",
            200,
            invalidGeometry: true);
        string entityType = Required(
            entity.EntityType,
            $"{prefix}.entity_type",
            32,
            invalidGeometry: true);
        string layer = Required(
            entity.Layer,
            $"{prefix}.layer",
            255,
            invalidGeometry: true);
        if (!entity.CreateLayerIfMissing.HasValue)
        {
            throw InvalidGeometry($"{prefix}.create_layer_if_missing is required.");
        }

        return entityType switch
        {
            "line" => PlanLine(
                entity,
                prefix,
                clientEntityId,
                layer,
                entity.CreateLayerIfMissing.Value),
            "polyline" => PlanPolyline(
                entity,
                prefix,
                clientEntityId,
                layer,
                entity.CreateLayerIfMissing.Value),
            _ => throw InvalidGeometry(
                $"{prefix}.entity_type must be 'line' or 'polyline'.")
        };
    }

    private static PlannedBatchEntity PlanLine(
        BatchEntity entity,
        string prefix,
        string clientEntityId,
        string layer,
        bool createLayerIfMissing)
    {
        if (entity.Vertices != null || entity.Closed.HasValue)
        {
            throw InvalidGeometry(
                $"{prefix} contains polyline fields on a line entity.");
        }

        BatchPlanPoint start = Point(entity.Start, $"{prefix}.start");
        BatchPlanPoint end = Point(entity.End, $"{prefix}.end");
        if (start == end)
        {
            throw InvalidGeometry(
                $"Line '{clientEntityId}' has zero length.");
        }

        return new PlannedBatchEntity(
            clientEntityId,
            "line",
            layer,
            createLayerIfMissing,
            start,
            end,
            null,
            false);
    }

    private static PlannedBatchEntity PlanPolyline(
        BatchEntity entity,
        string prefix,
        string clientEntityId,
        string layer,
        bool createLayerIfMissing)
    {
        if (entity.Start != null || entity.End != null)
        {
            throw InvalidGeometry(
                $"{prefix} contains line fields on a polyline entity.");
        }

        if (!entity.Closed.HasValue)
        {
            throw InvalidGeometry($"{prefix}.closed is required.");
        }

        List<BatchPoint3D> vertices = entity.Vertices ??
            throw InvalidGeometry($"{prefix}.vertices is required.");
        if (vertices.Count < 2)
        {
            throw InvalidGeometry(
                $"{prefix}.vertices must contain at least 2 points.");
        }

        if (vertices.Count > MaximumPoints)
        {
            throw LimitError(
                $"{prefix}.vertices exceeds the {MaximumPoints}-point batch limit.");
        }

        List<BatchPlanPoint> plannedVertices = new(vertices.Count);
        for (int vertexIndex = 0; vertexIndex < vertices.Count; vertexIndex++)
        {
            BatchPlanPoint vertex = Point(
                vertices[vertexIndex],
                $"{prefix}.vertices[{vertexIndex}]");
            if (vertexIndex > 0 && vertex == plannedVertices[^1])
            {
                throw InvalidGeometry(
                    $"Polyline '{clientEntityId}' has duplicate consecutive vertices.");
            }

            plannedVertices.Add(vertex);
        }

        if (entity.Closed.Value)
        {
            if (plannedVertices[0] == plannedVertices[^1])
            {
                throw InvalidGeometry(
                    $"Closed polyline '{clientEntityId}' must close without repeating its first vertex.");
            }

            if (plannedVertices.Distinct().Count() < 3)
            {
                throw InvalidGeometry(
                    $"Closed polyline '{clientEntityId}' needs at least three distinct vertices.");
            }
        }

        double elevation = plannedVertices[0].Z;
        if (plannedVertices.Any(vertex => vertex.Z != elevation))
        {
            throw InvalidGeometry(
                $"Polyline '{clientEntityId}' must have one constant Z elevation for LWPOLYLINE creation.");
        }

        return new PlannedBatchEntity(
            clientEntityId,
            "polyline",
            layer,
            createLayerIfMissing,
            null,
            null,
            plannedVertices,
            entity.Closed.Value);
    }

    private static BatchPlanPoint Point(BatchPoint3D? point, string propertyName)
    {
        if (point?.X is not double x ||
            point.Y is not double y ||
            point.Z is not double z ||
            !double.IsFinite(x) ||
            !double.IsFinite(y) ||
            !double.IsFinite(z))
        {
            throw InvalidGeometry(
                $"{propertyName} must contain finite x, y, and z values.");
        }

        return new BatchPlanPoint(x, y, z);
    }

    private static string Required(
        string? value,
        string propertyName,
        int maximumLength,
        bool invalidGeometry = false)
    {
        if (string.IsNullOrWhiteSpace(value) || value.Length > maximumLength)
        {
            string message =
                $"{propertyName} must contain 1 to {maximumLength} characters.";
            throw invalidGeometry
                ? InvalidGeometry(message)
                : InvalidCommand(message);
        }

        return value;
    }

    private static BatchContractException InvalidCommand(string message) =>
        new("INVALID_COMMAND", message);

    private static BatchContractException InvalidGeometry(string message) =>
        new("INVALID_BATCH_GEOMETRY", message);

    private static BatchContractException LimitError(string message) =>
        new("BATCH_LIMIT_EXCEEDED", message);
}

public static class BatchDocumentMatcher
{
    public static void Validate(
        BatchPlan plan,
        string actualDocumentName,
        Guid actualFingerprintGuid)
    {
        bool nameMatches = string.Equals(
            plan.ExpectedDocumentName,
            actualDocumentName,
            StringComparison.OrdinalIgnoreCase);
        bool fingerprintMatches =
            !plan.ExpectedFingerprintGuid.HasValue ||
            plan.ExpectedFingerprintGuid.Value == actualFingerprintGuid;
        if (nameMatches && fingerprintMatches)
        {
            return;
        }

        throw new BatchContractException(
            "DOCUMENT_MISMATCH",
            "The active document does not match the expected document.",
            new Dictionary<string, object?>
            {
                ["expected_name"] = plan.ExpectedDocumentName,
                ["actual_name"] = actualDocumentName,
                ["expected_fingerprint_guid"] =
                    plan.ExpectedFingerprintGuid?.ToString("D"),
                ["actual_fingerprint_guid"] =
                    actualFingerprintGuid.ToString("D")
            });
    }
}

public static class BatchLayerPlanner
{
    public static IReadOnlyList<PlannedLayerAction> Create(
        BatchPlan plan,
        IEnumerable<string> existingLayers)
    {
        HashSet<string> existing = new(
            existingLayers,
            StringComparer.OrdinalIgnoreCase);
        List<PlannedLayerAction> actions = [];

        foreach (IGrouping<string, PlannedBatchEntity> layerGroup in
                 plan.Entities.GroupBy(
                     entity => entity.Layer,
                     StringComparer.OrdinalIgnoreCase))
        {
            string layer = layerGroup.First().Layer;
            if (existing.Contains(layer))
            {
                actions.Add(new PlannedLayerAction(layer, "existing"));
                continue;
            }

            PlannedBatchEntity? blocked =
                layerGroup.FirstOrDefault(entity => !entity.CreateLayerIfMissing);
            if (blocked != null)
            {
                throw new BatchContractException(
                    "LAYER_POLICY_ERROR",
                    $"Layer '{layer}' does not exist and entity " +
                    $"'{blocked.ClientEntityId}' has create_layer_if_missing false.",
                    new Dictionary<string, object?>
                    {
                        ["layer"] = layer,
                        ["client_entity_id"] = blocked.ClientEntityId
                    });
            }

            actions.Add(new PlannedLayerAction(layer, "would_create"));
        }

        return actions;
    }
}

#if DEBUG
internal static class BatchFailureInjection
{
    internal static int? FailAfterStagedEntities { get; set; }

    internal static void ThrowIfRequested(
        int stagedEntityCount,
        string clientEntityId)
    {
        if (FailAfterStagedEntities == stagedEntityCount)
        {
            throw new InvalidOperationException(
                $"Injected test failure after staging {stagedEntityCount} " +
                $"entities at '{clientEntityId}'.");
        }
    }

    internal static void Reset() => FailAfterStagedEntities = null;
}
#endif
