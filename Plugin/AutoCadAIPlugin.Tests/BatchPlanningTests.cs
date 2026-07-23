using System.Text.Json;
using AutoCadAIPlugin.Models;
using AutoCadAIPlugin.Services;
using Microsoft.VisualStudio.TestTools.UnitTesting;

namespace AutoCadAIPlugin.Tests;

[TestClass]
public sealed class BatchPlanningTests
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true
    };

    [TestMethod]
    public void CanonicalFixtureCreatesExpectedPlan()
    {
        string fixture = Path.Combine(
            AppContext.BaseDirectory,
            "Fixtures",
            "execute-batch-v0.4.json");
        CadPayload payload = JsonSerializer.Deserialize<CadPayload>(
            File.ReadAllText(fixture),
            JsonOptions)!;

        BatchPlan plan = BatchPlanner.Create(payload);

        Assert.AreEqual(2, plan.Entities.Count);
        Assert.AreEqual(5, plan.TotalPointCount);
        Assert.AreEqual("line", plan.Entities[0].EntityType);
        Assert.AreEqual("polyline", plan.Entities[1].EntityType);
        Assert.IsFalse(plan.ValidateOnly);
    }

    [TestMethod]
    [DataRow("create-line-v0.1.json", "0.1", "create_line")]
    [DataRow(
        "get-drawing-context-v0.3.json",
        "0.3",
        "get_drawing_context")]
    public void LegacyRequestModelsStillDeserialize(
        string fixtureName,
        string schemaVersion,
        string operation)
    {
        string fixture = Path.Combine(
            AppContext.BaseDirectory,
            "Fixtures",
            fixtureName);
        CadPayload payload = JsonSerializer.Deserialize<CadPayload>(
            File.ReadAllText(fixture),
            JsonOptions)!;

        Assert.AreEqual(schemaVersion, payload.SchemaVersion);
        Assert.AreEqual(operation, payload.Operation);
        Assert.AreEqual(false, payload.RequiresApproval);
    }

    [TestMethod]
    [DataRow(1)]
    [DataRow(500)]
    public void EntityCountBoundariesAreAccepted(int entityCount)
    {
        CadPayload payload = ValidPayload();
        payload.Parameters.Entities = Enumerable.Range(0, entityCount)
            .Select(Line)
            .ToList();

        BatchPlan plan = BatchPlanner.Create(payload);

        Assert.AreEqual(entityCount, plan.Entities.Count);
        Assert.AreEqual(entityCount * 2, plan.TotalPointCount);
    }

    [TestMethod]
    [DataRow(0)]
    [DataRow(501)]
    public void EntityCountOutsideBoundariesIsRejected(int entityCount)
    {
        CadPayload payload = ValidPayload();
        payload.Parameters.Entities = Enumerable.Range(0, entityCount)
            .Select(Line)
            .ToList();

        BatchContractException exception = Assert.ThrowsException<BatchContractException>(
            () => BatchPlanner.Create(payload));

        Assert.AreEqual("BATCH_LIMIT_EXCEEDED", exception.Code);
    }

    [TestMethod]
    public void ExactPointLimitIsAccepted()
    {
        CadPayload payload = ValidPayload();
        payload.Parameters.Entities =
        [
            Polyline(50_000)
        ];

        BatchPlan plan = BatchPlanner.Create(payload);

        Assert.AreEqual(50_000, plan.TotalPointCount);
    }

    [TestMethod]
    public void PointLimitPlusOneIsRejected()
    {
        CadPayload payload = ValidPayload();
        payload.Parameters.Entities =
        [
            Polyline(50_001)
        ];

        BatchContractException exception = Assert.ThrowsException<BatchContractException>(
            () => BatchPlanner.Create(payload));

        Assert.AreEqual("BATCH_LIMIT_EXCEEDED", exception.Code);
    }

    [TestMethod]
    public void DuplicateClientEntityIdIsRejected()
    {
        CadPayload payload = ValidPayload();
        payload.Parameters.Entities = [Line(1), Line(1)];

        BatchContractException exception = Assert.ThrowsException<BatchContractException>(
            () => BatchPlanner.Create(payload));

        Assert.AreEqual("INVALID_BATCH_GEOMETRY", exception.Code);
        StringAssert.Contains(exception.Message, "Duplicate client_entity_id");
    }

    [TestMethod]
    public void ZeroLengthLineIsRejected()
    {
        CadPayload payload = ValidPayload();
        BatchEntity line = Line(1);
        line.End = line.Start;
        payload.Parameters.Entities = [line];

        BatchContractException exception = Assert.ThrowsException<BatchContractException>(
            () => BatchPlanner.Create(payload));

        Assert.AreEqual("INVALID_BATCH_GEOMETRY", exception.Code);
        StringAssert.Contains(exception.Message, "zero length");
    }

    [TestMethod]
    public void NonFiniteCoordinateIsRejected()
    {
        CadPayload payload = ValidPayload();
        BatchEntity line = Line(1);
        line.Start!.X = double.PositiveInfinity;
        payload.Parameters.Entities = [line];

        BatchContractException exception = Assert.ThrowsException<BatchContractException>(
            () => BatchPlanner.Create(payload));

        Assert.AreEqual("INVALID_BATCH_GEOMETRY", exception.Code);
        StringAssert.Contains(exception.Message, "finite");
    }

    [TestMethod]
    public void MissingCoordinateIsRejected()
    {
        CadPayload payload = ValidPayload();
        BatchEntity line = Line(1);
        line.Start!.Z = null;
        payload.Parameters.Entities = [line];

        BatchContractException exception = Assert.ThrowsException<BatchContractException>(
            () => BatchPlanner.Create(payload));

        Assert.AreEqual("INVALID_BATCH_GEOMETRY", exception.Code);
        StringAssert.Contains(exception.Message, "finite");
    }

    [TestMethod]
    public void InvalidLastEntityProvesFullBatchPreflight()
    {
        CadPayload payload = ValidPayload();
        BatchEntity invalidLast = Line(500);
        invalidLast.End = invalidLast.Start;
        payload.Parameters.Entities =
        [
            Line(1),
            Line(2),
            invalidLast
        ];

        BatchContractException exception = Assert.ThrowsException<BatchContractException>(
            () => BatchPlanner.Create(payload));

        Assert.AreEqual("INVALID_BATCH_GEOMETRY", exception.Code);
        StringAssert.Contains(exception.Message, "line-500");
    }

    [TestMethod]
    public void ConsecutiveDuplicatePolylineVertexIsRejected()
    {
        CadPayload payload = ValidPayload();
        BatchEntity polyline = Polyline(3);
        polyline.Vertices![1] = polyline.Vertices[0];
        payload.Parameters.Entities = [polyline];

        BatchContractException exception = Assert.ThrowsException<BatchContractException>(
            () => BatchPlanner.Create(payload));

        Assert.AreEqual("INVALID_BATCH_GEOMETRY", exception.Code);
        StringAssert.Contains(exception.Message, "duplicate consecutive");
    }

    [TestMethod]
    public void ClosedPolylineMustNotRepeatFirstVertex()
    {
        CadPayload payload = ValidPayload();
        BatchEntity polyline = Polyline(3);
        polyline.Closed = true;
        polyline.Vertices!.Add(polyline.Vertices[0]);
        payload.Parameters.Entities = [polyline];

        BatchContractException exception = Assert.ThrowsException<BatchContractException>(
            () => BatchPlanner.Create(payload));

        Assert.AreEqual("INVALID_BATCH_GEOMETRY", exception.Code);
        StringAssert.Contains(exception.Message, "without repeating");
    }

    [TestMethod]
    public void ClosedPolylineNeedsThreeDistinctVertices()
    {
        CadPayload payload = ValidPayload();
        BatchEntity polyline = Polyline(2);
        polyline.Closed = true;
        payload.Parameters.Entities = [polyline];

        BatchContractException exception = Assert.ThrowsException<BatchContractException>(
            () => BatchPlanner.Create(payload));

        Assert.AreEqual("INVALID_BATCH_GEOMETRY", exception.Code);
        StringAssert.Contains(exception.Message, "three distinct");
    }

    [TestMethod]
    public void LightweightPolylineRequiresConstantElevation()
    {
        CadPayload payload = ValidPayload();
        BatchEntity polyline = Polyline(3);
        polyline.Vertices![2].Z = 1;
        payload.Parameters.Entities = [polyline];

        BatchContractException exception = Assert.ThrowsException<BatchContractException>(
            () => BatchPlanner.Create(payload));

        Assert.AreEqual("INVALID_BATCH_GEOMETRY", exception.Code);
        StringAssert.Contains(exception.Message, "constant Z");
    }

    [TestMethod]
    public void MissingLayerWithoutCreationPolicyIsRejected()
    {
        CadPayload payload = ValidPayload();
        payload.Parameters.Entities = [Line(1)];
        payload.Parameters.Entities[0].CreateLayerIfMissing = false;
        BatchPlan plan = BatchPlanner.Create(payload);

        BatchContractException exception = Assert.ThrowsException<BatchContractException>(
            () => BatchLayerPlanner.Create(plan, ["0"]));

        Assert.AreEqual("LAYER_POLICY_ERROR", exception.Code);
    }

    [TestMethod]
    public void MissingLayerPolicyFieldIsRejected()
    {
        CadPayload payload = ValidPayload();
        payload.Parameters.Entities![0].CreateLayerIfMissing = null;

        BatchContractException exception = Assert.ThrowsException<BatchContractException>(
            () => BatchPlanner.Create(payload));

        Assert.AreEqual("INVALID_BATCH_GEOMETRY", exception.Code);
        StringAssert.Contains(exception.Message, "create_layer_if_missing");
    }

    [TestMethod]
    public void LayerPlanDistinguishesExistingAndNewLayers()
    {
        CadPayload payload = ValidPayload();
        BatchEntity existing = Line(1);
        existing.Layer = "0";
        BatchEntity missing = Line(2);
        missing.Layer = "AI-NEW";
        payload.Parameters.Entities = [existing, missing];
        BatchPlan plan = BatchPlanner.Create(payload);

        IReadOnlyList<PlannedLayerAction> actions =
            BatchLayerPlanner.Create(plan, ["0"]);

        CollectionAssert.AreEqual(
            new[] { "existing", "would_create" },
            actions.Select(action => action.Action).ToArray());
    }

    [TestMethod]
    public void DocumentNameComparisonIsCaseInsensitive()
    {
        BatchPlan plan = BatchPlanner.Create(ValidPayload());

        BatchDocumentMatcher.Validate(
            plan,
            "drawing1.DWG",
            Guid.Parse("11111111-1111-1111-1111-111111111111"));
    }

    [TestMethod]
    public void DocumentFingerprintMismatchIsRejected()
    {
        BatchPlan plan = BatchPlanner.Create(ValidPayload());

        BatchContractException exception = Assert.ThrowsException<BatchContractException>(
            () => BatchDocumentMatcher.Validate(
                plan,
                "Drawing1.dwg",
                Guid.Parse("22222222-2222-2222-2222-222222222222")));

        Assert.AreEqual("DOCUMENT_MISMATCH", exception.Code);
    }

    [TestMethod]
    public void ValidateOnlyFlagIsPreservedInPlan()
    {
        CadPayload payload = ValidPayload();
        payload.Parameters.ValidateOnly = true;

        BatchPlan plan = BatchPlanner.Create(payload);

        Assert.IsTrue(plan.ValidateOnly);
    }

    [TestMethod]
    public void DebugFailureHookTripsAtConfiguredEntityCount()
    {
        try
        {
            BatchFailureInjection.FailAfterStagedEntities = 2;
            BatchFailureInjection.ThrowIfRequested(1, "line-1");
            Assert.ThrowsException<InvalidOperationException>(
                () => BatchFailureInjection.ThrowIfRequested(2, "line-2"));
        }
        finally
        {
            BatchFailureInjection.Reset();
        }
    }

    [TestMethod]
    public void BatchResponseSerializesCorrelationFields()
    {
        CadResponse response = new()
        {
            SchemaVersion = "0.4",
            RunId = "run-1",
            ImportId = "import-1",
            CommandId = "cmd-1",
            Application = "autocad",
            Operation = "execute_batch",
            Status = "success",
            Message = "Validated.",
            Data = new BatchResponseData
            {
                ValidateOnly = true,
                ValidatedCount = 1,
                CreatedCount = 0,
                RolledBack = false,
                EntityResults =
                [
                    new BatchEntityResult
                    {
                        ClientEntityId = "line-1",
                        EntityType = "line",
                        Status = "validated",
                        ObjectId = null,
                        Layer = "AI-BATCH"
                    }
                ]
            },
            Document = new CadDocumentInfo
            {
                Name = "Drawing1.dwg",
                FingerprintGuid = "11111111-1111-1111-1111-111111111111"
            },
            ReportedPluginVersion = CadResponse.PluginVersion,
            CompletedAt = DateTimeOffset.UtcNow.ToString("O")
        };

        using JsonDocument json = JsonDocument.Parse(
            JsonSerializer.Serialize(response));
        JsonElement root = json.RootElement;

        Assert.AreEqual("0.4.0", root.GetProperty("plugin_version").GetString());
        Assert.AreEqual(
            JsonValueKind.Null,
            root.GetProperty("error").ValueKind);
        Assert.AreEqual(
            "import-1",
            root.GetProperty("import_id").GetString());
        Assert.AreEqual(
            "line-1",
            root.GetProperty("data")
                .GetProperty("entity_results")[0]
                .GetProperty("client_entity_id")
                .GetString());
        Assert.AreEqual(
            JsonValueKind.Null,
            root.GetProperty("data")
                .GetProperty("entity_results")[0]
                .GetProperty("object_id")
                .ValueKind);
    }

    private static CadPayload ValidPayload() =>
        new()
        {
            SchemaVersion = "0.4",
            RunId = "run-1",
            ImportId = "import-1",
            CommandId = "cmd-1",
            SubmittedAt = "2026-07-23T12:00:00Z",
            Application = "autocad",
            Operation = "execute_batch",
            Parameters = new CadParameters
            {
                ValidateOnly = false,
                ExpectedDocument = new BatchExpectedDocument
                {
                    Name = "Drawing1.dwg",
                    FingerprintGuid =
                        "11111111-1111-1111-1111-111111111111"
                },
                Entities = [Line(1)]
            },
            Units = "inches",
            CoordinateSystem = "world",
            RequiresApproval = false
        };

    private static BatchEntity Line(int index) =>
        new()
        {
            ClientEntityId = $"line-{index}",
            EntityType = "line",
            Layer = "AI-BATCH",
            CreateLayerIfMissing = true,
            Start = Point(index * 2, 0, 0),
            End = Point(index * 2 + 1, 0, 0)
        };

    private static BatchEntity Polyline(int pointCount) =>
        new()
        {
            ClientEntityId = "polyline-1",
            EntityType = "polyline",
            Layer = "AI-BATCH",
            CreateLayerIfMissing = true,
            Vertices = Enumerable.Range(0, pointCount)
                .Select(index => Point(index, 10, 0))
                .ToList(),
            Closed = false
        };

    private static BatchPoint3D Point(double x, double y, double z) =>
        new()
        {
            X = x,
            Y = y,
            Z = z
        };
}
