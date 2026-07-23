using AutoCadAIPlugin.Models;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;
using Application = Autodesk.AutoCAD.ApplicationServices.Application;

namespace AutoCadAIPlugin.Services;

public sealed class DrawingService
{
    public CadResponse CreateLine(CadPayload payload)
    {
        Validate(payload);

        Document doc = Application.DocumentManager.MdiActiveDocument;
        if (doc == null)
        {
            throw new CadRequestException(
                "NO_ACTIVE_DOCUMENT",
                "No active AutoCAD drawing is available.");
        }

        Database db = doc.Database;
        CadParameters parameters = payload.Parameters;
        List<string> warnings = [];
        double conversionFactor = GetConversionFactor(payload.Units, db.Insunits, warnings);

        Point3d startPoint = ConvertPoint(parameters.Start, conversionFactor);
        Point3d endPoint = ConvertPoint(parameters.End, conversionFactor);

        if (startPoint.IsEqualTo(endPoint))
        {
            throw new CadRequestException("A line must have different start and end points.");
        }

        bool isVersionTwo = payload.SchemaVersion == "0.2";
        string objectHandle;
        using (Transaction transaction = db.TransactionManager.StartTransaction())
        {
            LayerTable layerTable =
                (LayerTable)transaction.GetObject(db.LayerTableId, OpenMode.ForRead);
            ObjectId layerId;

            if (layerTable.Has(parameters.Layer))
            {
                layerId = layerTable[parameters.Layer];
            }
            else if (parameters.CreateLayerIfMissing)
            {
                layerTable.UpgradeOpen();
                using LayerTableRecord layer = new() { Name = parameters.Layer };
                layerId = layerTable.Add(layer);
                transaction.AddNewlyCreatedDBObject(layer, true);
            }
            else
            {
                throw new CadRequestException(
                    $"Layer '{parameters.Layer}' does not exist and create_layer_if_missing is false.");
            }

            BlockTable blockTable =
                (BlockTable)transaction.GetObject(db.BlockTableId, OpenMode.ForRead);
            BlockTableRecord modelSpace = (BlockTableRecord)transaction.GetObject(
                blockTable[BlockTableRecord.ModelSpace], OpenMode.ForWrite);

            using Line line = new(startPoint, endPoint) { LayerId = layerId };
            modelSpace.AppendEntity(line);
            transaction.AddNewlyCreatedDBObject(line, true);
            if (isVersionTwo)
            {
                AttachProvenance(line, payload, db, transaction);
            }
            objectHandle = line.ObjectId.Handle.ToString();

            transaction.Commit();
        }

        return new CadResponse
        {
            SchemaVersion = payload.SchemaVersion,
            RunId = isVersionTwo ? payload.RunId : null,
            ImportId = isVersionTwo ? payload.ImportId : null,
            CommandId = payload.CommandId,
            Application = isVersionTwo ? payload.Application : null,
            Operation = isVersionTwo ? payload.Operation : null,
            Status = "success",
            Message = "Line created successfully.",
            Error = null,
            AffectedObjects =
            [
                new AffectedObject
                {
                    ObjectType = "LINE",
                    ObjectId = objectHandle,
                    Action = "created"
                }
            ],
            Data = new LineResponseData
            {
                Layer = parameters.Layer,
                StartInDrawingUnits = [startPoint.X, startPoint.Y, startPoint.Z],
                EndInDrawingUnits = [endPoint.X, endPoint.Y, endPoint.Z]
            },
            UndoToken = CreateUndoToken(payload.CommandId),
            Warnings = warnings,
            Document = isVersionTwo
                ? new CadDocumentInfo { Name = Path.GetFileName(doc.Name) }
                : null,
            ReportedPluginVersion = isVersionTwo ? CadResponse.PluginVersion : null,
            CompletedAt = isVersionTwo
                ? DateTimeOffset.UtcNow.ToString("O")
                : null
        };
    }

    private static void Validate(CadPayload payload)
    {
        if (payload == null)
        {
            throw new CadRequestException("The JSON request body is required.");
        }

        if (payload.SchemaVersion is not ("0.1" or "0.2"))
        {
            throw new CadRequestException(
                "UNSUPPORTED_SCHEMA_VERSION",
                "Unsupported schema_version. Expected '0.1' or '0.2'.");
        }

        if (payload.SchemaVersion == "0.2")
        {
            if (string.IsNullOrWhiteSpace(payload.RunId))
            {
                throw new CadRequestException("run_id is required for schema v0.2.");
            }

            if (string.IsNullOrWhiteSpace(payload.SubmittedAt) ||
                !DateTimeOffset.TryParse(payload.SubmittedAt, out _))
            {
                throw new CadRequestException(
                    "submitted_at must be a valid timestamp for schema v0.2.");
            }
        }

        if (string.IsNullOrWhiteSpace(payload.CommandId))
        {
            throw new CadRequestException("command_id is required.");
        }

        if (!string.Equals(payload.Application, "autocad", StringComparison.OrdinalIgnoreCase))
        {
            throw new CadRequestException("application must be 'autocad'.");
        }

        if (!string.Equals(payload.Operation, "create_line", StringComparison.OrdinalIgnoreCase))
        {
            throw new CadRequestException($"Unsupported operation '{payload.Operation}'.");
        }

        if (!string.Equals(payload.CoordinateSystem, "world", StringComparison.OrdinalIgnoreCase))
        {
            throw new CadRequestException(
                "Only the 'world' coordinate_system is supported in this proof of concept.");
        }

        if (payload.RequiresApproval)
        {
            throw new CadRequestException(
                "This request requires approval and was not executed. Resubmit it with requires_approval set to false after approval.");
        }

        if (payload.Parameters == null)
        {
            throw new CadRequestException("parameters is required.");
        }

        if (string.IsNullOrWhiteSpace(payload.Parameters.Layer))
        {
            throw new CadRequestException("parameters.layer is required.");
        }

        if (string.IsNullOrWhiteSpace(payload.Units))
        {
            throw new CadRequestException("units is required.");
        }

        ValidatePoint(payload.Parameters.Start, "parameters.start");
        ValidatePoint(payload.Parameters.End, "parameters.end");
    }

    private static void ValidatePoint(Point3D? point, string propertyName)
    {
        if (point == null ||
            !double.IsFinite(point.X) ||
            !double.IsFinite(point.Y) ||
            !double.IsFinite(point.Z))
        {
            throw new CadRequestException(
                $"{propertyName} must contain finite x, y, and z values.");
        }
    }

    private static Point3d ConvertPoint(Point3D point, double factor) =>
        new(point.X * factor, point.Y * factor, point.Z * factor);

    private static double GetConversionFactor(
        string requestUnits,
        UnitsValue drawingUnits,
        ICollection<string> warnings)
    {
        UnitsValue sourceUnits = requestUnits.Trim().ToLowerInvariant() switch
        {
            "inch" or "inches" => UnitsValue.Inches,
            "foot" or "feet" => UnitsValue.Feet,
            "millimeter" or "millimeters" or "mm" => UnitsValue.Millimeters,
            "centimeter" or "centimeters" or "cm" => UnitsValue.Centimeters,
            "meter" or "meters" or "m" => UnitsValue.Meters,
            _ => throw new CadRequestException(
                $"Unsupported units '{requestUnits}'. Supported values are inches, feet, millimeters, centimeters, and meters.")
        };

        UnitsValue targetUnits = drawingUnits;
        if (targetUnits == UnitsValue.Undefined)
        {
            targetUnits = UnitsValue.Inches;
            warnings.Add("The drawing INSUNITS value is Unitless; inches were assumed for conversion.");
        }

        return UnitsConverter.GetConversionFactor(sourceUnits, targetUnits);
    }

    private static string CreateUndoToken(string commandId)
    {
        const string commandPrefix = "cmd-";
        string suffix = commandId.StartsWith(commandPrefix, StringComparison.OrdinalIgnoreCase)
            ? commandId[commandPrefix.Length..]
            : commandId;

        return $"ai-action-{suffix}";
    }

    private static void AttachProvenance(
        Entity entity,
        CadPayload payload,
        Database database,
        Transaction transaction)
    {
        RegAppTable registrationTable = (RegAppTable)transaction.GetObject(
            database.RegAppTableId,
            OpenMode.ForRead);
        if (!registrationTable.Has(ReadOnlyDrawingService.ProvenanceApplicationName))
        {
            registrationTable.UpgradeOpen();
            using RegAppTableRecord registration = new()
            {
                Name = ReadOnlyDrawingService.ProvenanceApplicationName
            };
            registrationTable.Add(registration);
            transaction.AddNewlyCreatedDBObject(registration, true);
        }

        List<TypedValue> values =
        [
            new(
                (int)DxfCode.ExtendedDataRegAppName,
                ReadOnlyDrawingService.ProvenanceApplicationName),
            new((int)DxfCode.ExtendedDataAsciiString, "run_id"),
            new((int)DxfCode.ExtendedDataAsciiString, payload.RunId!),
            new((int)DxfCode.ExtendedDataAsciiString, "command_id"),
            new((int)DxfCode.ExtendedDataAsciiString, payload.CommandId)
        ];
        if (!string.IsNullOrWhiteSpace(payload.ImportId))
        {
            values.Add(new TypedValue(
                (int)DxfCode.ExtendedDataAsciiString,
                "import_id"));
            values.Add(new TypedValue(
                (int)DxfCode.ExtendedDataAsciiString,
                payload.ImportId));
        }

        using ResultBuffer provenance = new(values.ToArray());
        entity.XData = provenance;
    }
}

public sealed class CadRequestException : Exception
{
    public CadRequestException(string message)
        : this("INVALID_COMMAND", message)
    {
    }

    public CadRequestException(string code, string message)
        : base(message)
    {
        Code = code;
    }

    public string Code { get; }
}
