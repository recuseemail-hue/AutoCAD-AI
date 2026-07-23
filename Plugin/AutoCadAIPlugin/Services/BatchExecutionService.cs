using AutoCadAIPlugin.Models;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;
using Application = Autodesk.AutoCAD.ApplicationServices.Application;

namespace AutoCadAIPlugin.Services;

public sealed class BatchExecutionService
{
    public CadResponse Execute(
        CadPayload payload,
        CancellationToken cancellationToken = default)
    {
        Document? document = Application.DocumentManager.MdiActiveDocument;
        BatchPlan? plan = null;
        try
        {
            plan = BatchPlanner.Create(payload);
            if (document == null)
            {
                return Error(
                    payload,
                    "NO_ACTIVE_DOCUMENT",
                    "No active AutoCAD drawing is available.",
                    null,
                    null,
                    plan.ValidateOnly,
                    0,
                    false);
            }

            string documentName = Path.GetFileName(document.Name);
            Guid fingerprint = GetFingerprint(document.Database);
            BatchDocumentMatcher.Validate(plan, documentName, fingerprint);
            cancellationToken.ThrowIfCancellationRequested();

            IReadOnlyList<PlannedLayerAction> layerActions =
                Preflight(document.Database, plan);
            if (plan.ValidateOnly)
            {
                return ValidationSuccess(
                    payload,
                    plan,
                    documentName,
                    fingerprint,
                    layerActions,
                    UnitWarnings(document.Database));
            }

            if (document.IsReadOnly)
            {
                return Error(
                    payload,
                    "BATCH_EXECUTION_FAILED",
                    "The active document is read-only.",
                    null,
                    DocumentInfo(documentName, fingerprint),
                    false,
                    plan.Entities.Count,
                    true);
            }

            return ExecuteWrite(
                payload,
                plan,
                document.Database,
                documentName,
                fingerprint,
                UnitWarnings(document.Database),
                cancellationToken);
        }
        catch (BatchContractException exception)
        {
            Guid? fingerprint = document == null
                ? null
                : GetFingerprint(document.Database);
            string? documentName = document == null
                ? null
                : Path.GetFileName(document.Name);
            return Error(
                payload,
                exception.Code,
                exception.Message,
                exception.Details,
                documentName == null || !fingerprint.HasValue
                    ? null
                    : DocumentInfo(documentName, fingerprint.Value),
                plan?.ValidateOnly ?? payload.Parameters?.ValidateOnly ?? false,
                0,
                false);
        }
    }

    private static IReadOnlyList<PlannedLayerAction> Preflight(
        Database database,
        BatchPlan plan)
    {
        _ = GetConversionFactor(plan.Units, database.Insunits);
        using Transaction transaction =
            database.TransactionManager.StartOpenCloseTransaction();
        if (!plan.ValidateOnly)
        {
            EnsureCommandIsNew(database, transaction, plan.CommandId);
        }

        ValidateLayerNames(plan);
        IReadOnlyList<PlannedLayerAction> actions = BatchLayerPlanner.Create(
            plan,
            GetLayerNames(database, transaction));
        return actions;
    }

    private static CadResponse ExecuteWrite(
        CadPayload payload,
        BatchPlan plan,
        Database database,
        string documentName,
        Guid fingerprint,
        IReadOnlyList<string> warnings,
        CancellationToken cancellationToken)
    {
        string? failedClientEntityId = null;
        try
        {
            using Transaction transaction =
                database.TransactionManager.StartTransaction();
            EnsureCommandIsNew(database, transaction, plan.CommandId);
            ValidateLayerNames(plan);

            LayerTable layerTable = (LayerTable)transaction.GetObject(
                database.LayerTableId,
                OpenMode.ForRead);
            IReadOnlyList<PlannedLayerAction> layerActions =
                BatchLayerPlanner.Create(plan, LayerNames(layerTable, transaction));
            Dictionary<string, ObjectId> layerIds =
                EnsureLayers(layerTable, transaction, layerActions);

            RegisterProvenanceApplication(database, transaction);
            BlockTable blockTable = (BlockTable)transaction.GetObject(
                database.BlockTableId,
                OpenMode.ForRead);
            BlockTableRecord modelSpace =
                (BlockTableRecord)transaction.GetObject(
                    blockTable[BlockTableRecord.ModelSpace],
                    OpenMode.ForWrite);
            double conversionFactor =
                GetConversionFactor(plan.Units, database.Insunits);

            List<BatchEntityResult> entityResults = [];
            List<AffectedObject> affectedObjects = [];
            int stagedEntityCount = 0;
            foreach (PlannedBatchEntity entityPlan in plan.Entities)
            {
                cancellationToken.ThrowIfCancellationRequested();
                failedClientEntityId = entityPlan.ClientEntityId;
                Entity entity = CreateEntity(entityPlan, conversionFactor);
                using (entity)
                {
                    entity.LayerId = layerIds[entityPlan.Layer];
                    modelSpace.AppendEntity(entity);
                    transaction.AddNewlyCreatedDBObject(entity, true);
                    AttachProvenance(entity, plan, entityPlan.ClientEntityId);

                    string handle = entity.ObjectId.Handle.ToString();
                    entityResults.Add(new BatchEntityResult
                    {
                        ClientEntityId = entityPlan.ClientEntityId,
                        EntityType = entityPlan.EntityType,
                        Status = "created",
                        ObjectId = handle,
                        Layer = entityPlan.Layer
                    });
                    affectedObjects.Add(new AffectedObject
                    {
                        ClientEntityId = entityPlan.ClientEntityId,
                        ObjectType = entityPlan.EntityType == "line"
                            ? "LINE"
                            : "LWPOLYLINE",
                        ObjectId = handle,
                        Action = "created"
                    });
                }

                stagedEntityCount++;
#if DEBUG
                BatchFailureInjection.ThrowIfRequested(
                    stagedEntityCount,
                    entityPlan.ClientEntityId);
#endif
            }

            cancellationToken.ThrowIfCancellationRequested();
            transaction.Commit();

            return new CadResponse
            {
                SchemaVersion = payload.SchemaVersion,
                RunId = plan.RunId,
                ImportId = plan.ImportId,
                CommandId = plan.CommandId,
                Application = payload.Application,
                Operation = payload.Operation,
                Status = "success",
                Message = "Atomic batch created successfully.",
                Error = null,
                AffectedObjects = affectedObjects,
                Data = new BatchResponseData
                {
                    ValidateOnly = false,
                    ValidatedCount = plan.Entities.Count,
                    CreatedCount = plan.Entities.Count,
                    RolledBack = false,
                    EntityResults = entityResults,
                    LayerActions = layerActions
                        .Select(action => new BatchLayerAction
                        {
                            Layer = action.Layer,
                            Action = action.Action == "would_create"
                                ? "created"
                                : action.Action
                        })
                        .ToArray()
                },
                UndoToken = $"ai-batch-{plan.CommandId}",
                Warnings = warnings,
                Document = DocumentInfo(documentName, fingerprint),
                ReportedPluginVersion = CadResponse.PluginVersion,
                CompletedAt = DateTimeOffset.UtcNow.ToString("O")
            };
        }
        catch (BatchContractException exception)
        {
            return Error(
                payload,
                exception.Code,
                exception.Message,
                exception.Details,
                DocumentInfo(documentName, fingerprint),
                false,
                plan.Entities.Count,
                false);
        }
        catch (Exception exception)
        {
            Dictionary<string, object?> details = new()
            {
                ["failed_client_entity_id"] = failedClientEntityId,
                ["exception_type"] = exception.GetType().Name
            };
            return Error(
                payload,
                "BATCH_ROLLED_BACK",
                "Batch execution failed and the transaction was rolled back.",
                details,
                DocumentInfo(documentName, fingerprint),
                false,
                plan.Entities.Count,
                true);
        }
    }

    private static CadResponse ValidationSuccess(
        CadPayload payload,
        BatchPlan plan,
        string documentName,
        Guid fingerprint,
        IReadOnlyList<PlannedLayerAction> layerActions,
        IReadOnlyList<string> warnings) =>
        new()
        {
            SchemaVersion = payload.SchemaVersion,
            RunId = plan.RunId,
            ImportId = plan.ImportId,
            CommandId = plan.CommandId,
            Application = payload.Application,
            Operation = payload.Operation,
            Status = "success",
            Message = "Atomic batch validated successfully.",
            Error = null,
            AffectedObjects = [],
            Data = new BatchResponseData
            {
                ValidateOnly = true,
                ValidatedCount = plan.Entities.Count,
                CreatedCount = 0,
                RolledBack = false,
                EntityResults = plan.Entities
                    .Select(entity => new BatchEntityResult
                    {
                        ClientEntityId = entity.ClientEntityId,
                        EntityType = entity.EntityType,
                        Status = "validated",
                        ObjectId = null,
                        Layer = entity.Layer
                    })
                    .ToArray(),
                LayerActions = layerActions
                    .Select(action => new BatchLayerAction
                    {
                        Layer = action.Layer,
                        Action = action.Action
                    })
                    .ToArray()
            },
            UndoToken = null,
            Warnings = warnings,
            Document = DocumentInfo(documentName, fingerprint),
            ReportedPluginVersion = CadResponse.PluginVersion,
            CompletedAt = DateTimeOffset.UtcNow.ToString("O")
        };

    private static CadResponse Error(
        CadPayload payload,
        string code,
        string message,
        IReadOnlyDictionary<string, object?>? details,
        CadDocumentInfo? document,
        bool validateOnly,
        int validatedCount,
        bool rolledBack) =>
        new()
        {
            SchemaVersion = payload.SchemaVersion,
            RunId = payload.RunId,
            ImportId = payload.ImportId,
            CommandId = payload.CommandId,
            Application = payload.Application,
            Operation = payload.Operation,
            Status = "error",
            Message = message,
            Error = new CadError
            {
                Code = code,
                Message = message,
                Details = details
            },
            AffectedObjects = [],
            Data = payload.SchemaVersion == "0.4"
                ? new BatchResponseData
                {
                    ValidateOnly = validateOnly,
                    ValidatedCount = validatedCount,
                    CreatedCount = 0,
                    RolledBack = rolledBack,
                    EntityResults = [],
                    LayerActions = null
                }
                : null,
            UndoToken = null,
            Warnings = [],
            Document = document,
            ReportedPluginVersion = CadResponse.PluginVersion,
            CompletedAt = DateTimeOffset.UtcNow.ToString("O")
        };

    private static Entity CreateEntity(
        PlannedBatchEntity plan,
        double conversionFactor)
    {
        if (plan.EntityType == "line")
        {
            return new Line(
                Point3d(plan.Start!, conversionFactor),
                Point3d(plan.End!, conversionFactor));
        }

        IReadOnlyList<BatchPlanPoint> vertices = plan.Vertices!;
        Polyline polyline = new(vertices.Count)
        {
            Closed = plan.Closed,
            Elevation = vertices[0].Z * conversionFactor
        };
        for (int index = 0; index < vertices.Count; index++)
        {
            BatchPlanPoint vertex = vertices[index];
            polyline.AddVertexAt(
                index,
                new Point2d(
                    vertex.X * conversionFactor,
                    vertex.Y * conversionFactor),
                0,
                0,
                0);
        }

        return polyline;
    }

    private static Point3d Point3d(
        BatchPlanPoint point,
        double conversionFactor) =>
        new(
            point.X * conversionFactor,
            point.Y * conversionFactor,
            point.Z * conversionFactor);

    private static Dictionary<string, ObjectId> EnsureLayers(
        LayerTable layerTable,
        Transaction transaction,
        IReadOnlyList<PlannedLayerAction> actions)
    {
        Dictionary<string, ObjectId> layerIds =
            new(StringComparer.OrdinalIgnoreCase);
        foreach (PlannedLayerAction action in actions)
        {
            if (action.Action == "existing")
            {
                layerIds[action.Layer] = layerTable[action.Layer];
                continue;
            }

            if (!layerTable.IsWriteEnabled)
            {
                layerTable.UpgradeOpen();
            }

            using LayerTableRecord layer = new() { Name = action.Layer };
            ObjectId layerId = layerTable.Add(layer);
            transaction.AddNewlyCreatedDBObject(layer, true);
            layerIds[action.Layer] = layerId;
        }

        return layerIds;
    }

    private static void ValidateLayerNames(BatchPlan plan)
    {
        foreach (string layer in plan.Entities
                     .Select(entity => entity.Layer)
                     .Distinct(StringComparer.OrdinalIgnoreCase))
        {
            try
            {
                SymbolUtilityServices.ValidateSymbolName(layer, false);
            }
            catch (Exception exception)
            {
                throw new BatchContractException(
                    "LAYER_POLICY_ERROR",
                    $"Layer '{layer}' is not a valid AutoCAD layer name.",
                    new Dictionary<string, object?>
                    {
                        ["layer"] = layer,
                        ["reason"] = exception.Message
                    });
            }
        }
    }

    private static IEnumerable<string> GetLayerNames(
        Database database,
        Transaction transaction)
    {
        LayerTable layerTable = (LayerTable)transaction.GetObject(
            database.LayerTableId,
            OpenMode.ForRead);
        return LayerNames(layerTable, transaction).ToArray();
    }

    private static IEnumerable<string> LayerNames(
        LayerTable layerTable,
        Transaction transaction)
    {
        foreach (ObjectId layerId in layerTable)
        {
            LayerTableRecord layer =
                (LayerTableRecord)transaction.GetObject(
                    layerId,
                    OpenMode.ForRead);
            yield return layer.Name;
        }
    }

    private static void EnsureCommandIsNew(
        Database database,
        Transaction transaction,
        string commandId)
    {
        BlockTable blockTable = (BlockTable)transaction.GetObject(
            database.BlockTableId,
            OpenMode.ForRead);
        BlockTableRecord modelSpace =
            (BlockTableRecord)transaction.GetObject(
                blockTable[BlockTableRecord.ModelSpace],
                OpenMode.ForRead);
        foreach (ObjectId objectId in modelSpace)
        {
            if (transaction.GetObject(objectId, OpenMode.ForRead) is not Entity entity)
            {
                continue;
            }

            using ResultBuffer? provenance = entity.GetXDataForApplication(
                ReadOnlyDrawingService.ProvenanceApplicationName);
            if (ProvenanceValue(provenance, "command_id") == commandId)
            {
                throw new BatchContractException(
                    "DUPLICATE_COMMAND",
                    $"Command '{commandId}' has already created drawing geometry.",
                    new Dictionary<string, object?>
                    {
                        ["command_id"] = commandId,
                        ["existing_object_id"] = entity.Handle.ToString()
                    });
            }
        }
    }

    private static string? ProvenanceValue(
        ResultBuffer? provenance,
        string requestedKey)
    {
        if (provenance == null)
        {
            return null;
        }

        TypedValue[] values = provenance.AsArray();
        for (int index = 1; index + 1 < values.Length; index += 2)
        {
            if (values[index].Value is string key &&
                key == requestedKey &&
                values[index + 1].Value is string value)
            {
                return value;
            }
        }

        return null;
    }

    private static void RegisterProvenanceApplication(
        Database database,
        Transaction transaction)
    {
        RegAppTable registrationTable = (RegAppTable)transaction.GetObject(
            database.RegAppTableId,
            OpenMode.ForRead);
        if (registrationTable.Has(ReadOnlyDrawingService.ProvenanceApplicationName))
        {
            return;
        }

        registrationTable.UpgradeOpen();
        using RegAppTableRecord registration = new()
        {
            Name = ReadOnlyDrawingService.ProvenanceApplicationName
        };
        registrationTable.Add(registration);
        transaction.AddNewlyCreatedDBObject(registration, true);
    }

    private static void AttachProvenance(
        Entity entity,
        BatchPlan plan,
        string clientEntityId)
    {
        using ResultBuffer provenance = new(
            new TypedValue(
                (int)DxfCode.ExtendedDataRegAppName,
                ReadOnlyDrawingService.ProvenanceApplicationName),
            new TypedValue((int)DxfCode.ExtendedDataAsciiString, "run_id"),
            new TypedValue((int)DxfCode.ExtendedDataAsciiString, plan.RunId),
            new TypedValue((int)DxfCode.ExtendedDataAsciiString, "import_id"),
            new TypedValue((int)DxfCode.ExtendedDataAsciiString, plan.ImportId),
            new TypedValue((int)DxfCode.ExtendedDataAsciiString, "command_id"),
            new TypedValue((int)DxfCode.ExtendedDataAsciiString, plan.CommandId),
            new TypedValue(
                (int)DxfCode.ExtendedDataAsciiString,
                "client_entity_id"),
            new TypedValue(
                (int)DxfCode.ExtendedDataAsciiString,
                clientEntityId));
        entity.XData = provenance;
    }

    private static double GetConversionFactor(
        string requestUnits,
        UnitsValue drawingUnits)
    {
        UnitsValue sourceUnits = requestUnits switch
        {
            "inches" => UnitsValue.Inches,
            "feet" => UnitsValue.Feet,
            "millimeters" => UnitsValue.Millimeters,
            "centimeters" => UnitsValue.Centimeters,
            "meters" => UnitsValue.Meters,
            _ => throw new BatchContractException(
                "INVALID_COMMAND",
                $"Unsupported units '{requestUnits}'.")
        };
        UnitsValue targetUnits = drawingUnits == UnitsValue.Undefined
            ? UnitsValue.Inches
            : drawingUnits;
        return UnitsConverter.GetConversionFactor(sourceUnits, targetUnits);
    }

    private static CadDocumentInfo DocumentInfo(
        string documentName,
        Guid fingerprint) =>
        new()
        {
            Name = documentName,
            FingerprintGuid = fingerprint.ToString("D")
        };

    private static IReadOnlyList<string> UnitWarnings(Database database) =>
        database.Insunits == UnitsValue.Undefined
            ? [
                "The drawing INSUNITS value is Unitless; inches were assumed for conversion."
            ]
            : [];

    private static Guid GetFingerprint(Database database)
    {
        if (Guid.TryParse(database.FingerprintGuid, out Guid fingerprint))
        {
            return fingerprint;
        }

        return Guid.Empty;
    }
}
