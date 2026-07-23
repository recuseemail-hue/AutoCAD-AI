using System.Globalization;
using AutoCadAIPlugin.Models;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;
using Autodesk.AutoCAD.Runtime;
using Application = Autodesk.AutoCAD.ApplicationServices.Application;
using RuntimeException = Autodesk.AutoCAD.Runtime.Exception;

namespace AutoCadAIPlugin.Services;

public sealed class ReadOnlyDrawingService
{
    private const int DefaultLimit = 100;
    private const int MaximumLimit = 500;
    private const int MaximumPolylineVertices = 500;
    internal const string ProvenanceApplicationName = "AUTOCAD_AI";

    private static readonly HashSet<string> SupportedOperations =
    [
        "get_drawing_context",
        "get_active_document",
        "get_drawing_units",
        "get_current_coordinate_system",
        "get_drawing_extents",
        "list_layers",
        "get_selected_entities",
        "get_entities_in_window",
        "get_entity_properties",
        "find_entities_by_import_id"
    ];

    public CadResponse Execute(CadPayload payload)
    {
        Validate(payload);

        Document? document = Application.DocumentManager.MdiActiveDocument;
        if (document == null)
        {
            throw new CadRequestException(
                "NO_ACTIVE_DOCUMENT",
                "No active AutoCAD drawing is available.");
        }

        object data;
        List<string> warnings = [];
        using (Transaction transaction =
               document.Database.TransactionManager.StartOpenCloseTransaction())
        {
            data = payload.Operation switch
            {
                "get_drawing_context" =>
                    GetDrawingContext(document, transaction),
                "get_active_document" =>
                    GetActiveDocument(document),
                "get_drawing_units" =>
                    GetDrawingUnits(document.Database),
                "get_current_coordinate_system" =>
                    GetCoordinateSystem(document),
                "get_drawing_extents" =>
                    GetDrawingExtents(document.Database, transaction),
                "list_layers" =>
                    GetLayers(document.Database, transaction, GetLimit(payload), warnings),
                "get_selected_entities" =>
                    GetSelectedEntities(document, transaction, GetLimit(payload), warnings),
                "get_entities_in_window" =>
                    GetEntitiesInWindow(
                        document.Database,
                        transaction,
                        payload.Parameters.WindowMin!,
                        payload.Parameters.WindowMax!,
                        GetLimit(payload),
                        warnings),
                "get_entity_properties" =>
                    GetEntityProperties(
                        document.Database,
                        transaction,
                        payload.Parameters.ObjectId!),
                "find_entities_by_import_id" =>
                    FindEntitiesByImportId(
                        document.Database,
                        transaction,
                        payload.Parameters.TargetImportId!,
                        GetLimit(payload),
                        warnings),
                _ => throw new CadRequestException(
                    "UNSUPPORTED_OPERATION",
                    $"Unsupported read operation '{payload.Operation}'.")
            };
        }

        return new CadResponse
        {
            SchemaVersion = payload.SchemaVersion,
            RunId = payload.RunId,
            ImportId = payload.ImportId,
            CommandId = payload.CommandId,
            Application = payload.Application,
            Operation = payload.Operation,
            Status = "success",
            Message = ReadSuccessMessage(payload.Operation),
            Error = null,
            AffectedObjects = [],
            Data = data,
            UndoToken = null,
            Warnings = warnings,
            Document = new CadDocumentInfo
            {
                Name = Path.GetFileName(document.Name)
            },
            ReportedPluginVersion = CadResponse.PluginVersion,
            CompletedAt = DateTimeOffset.UtcNow.ToString("O")
        };
    }

    private static void Validate(CadPayload payload)
    {
        if (payload == null)
        {
            throw new CadRequestException("The JSON request body is required.");
        }

        if (payload.SchemaVersion != "0.3")
        {
            throw new CadRequestException(
                "UNSUPPORTED_SCHEMA_VERSION",
                "Read-only operations require schema_version '0.3'.");
        }

        if (string.IsNullOrWhiteSpace(payload.RunId))
        {
            throw new CadRequestException("run_id is required.");
        }

        if (string.IsNullOrWhiteSpace(payload.CommandId))
        {
            throw new CadRequestException("command_id is required.");
        }

        if (string.IsNullOrWhiteSpace(payload.SubmittedAt) ||
            !DateTimeOffset.TryParse(payload.SubmittedAt, out _))
        {
            throw new CadRequestException("submitted_at must be a valid timestamp.");
        }

        if (!string.Equals(payload.Application, "autocad", StringComparison.OrdinalIgnoreCase))
        {
            throw new CadRequestException("application must be 'autocad'.");
        }

        if (!SupportedOperations.Contains(payload.Operation))
        {
            throw new CadRequestException(
                "UNSUPPORTED_OPERATION",
                $"Unsupported read operation '{payload.Operation}'.");
        }

        if (payload.RequiresApproval)
        {
            throw new CadRequestException(
                "Read-only commands must set requires_approval to false.");
        }

        if (payload.Parameters == null)
        {
            throw new CadRequestException("parameters is required.");
        }

        if (payload.Parameters.Limit.HasValue &&
            payload.Parameters.Limit.Value is < 1 or > MaximumLimit)
        {
            throw new CadRequestException(
                $"parameters.limit must be between 1 and {MaximumLimit}.");
        }

        if (payload.Operation == "get_entities_in_window")
        {
            ValidateWindow(payload);
        }
        else if (payload.Operation == "get_entity_properties")
        {
            ParseHandle(payload.Parameters.ObjectId);
        }
        else if (payload.Operation == "find_entities_by_import_id" &&
                 string.IsNullOrWhiteSpace(payload.Parameters.TargetImportId))
        {
            throw new CadRequestException("parameters.target_import_id is required.");
        }
    }

    private static void ValidateWindow(CadPayload payload)
    {
        if (!string.Equals(
                payload.CoordinateSystem,
                "world",
                StringComparison.OrdinalIgnoreCase))
        {
            throw new CadRequestException(
                "get_entities_in_window requires coordinate_system 'world'.");
        }

        Point3D? minimum = payload.Parameters.WindowMin;
        Point3D? maximum = payload.Parameters.WindowMax;
        ValidatePoint(minimum, "parameters.window_min");
        ValidatePoint(maximum, "parameters.window_max");

        if (minimum!.X > maximum!.X ||
            minimum.Y > maximum.Y ||
            minimum.Z > maximum.Z)
        {
            throw new CadRequestException(
                "Each window_min coordinate must be less than or equal to window_max.");
        }
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

    private static int GetLimit(CadPayload payload) =>
        payload.Parameters.Limit ?? DefaultLimit;

    private static object GetDrawingContext(
        Document document,
        Transaction transaction)
    {
        Database database = document.Database;
        LayerTableRecord currentLayer = (LayerTableRecord)transaction.GetObject(
            database.Clayer,
            OpenMode.ForRead);

        return new Dictionary<string, object?>
        {
            ["document"] = GetActiveDocument(document),
            ["drawing_units"] = UnitName(database.Insunits),
            ["current_layer"] = currentLayer.Name,
            ["current_space"] = database.TileMode ? "model" : "paper",
            ["coordinate_system"] = GetCoordinateSystem(document),
            ["extents"] = GetDrawingExtents(database, transaction)
        };
    }

    private static object GetActiveDocument(Document document)
    {
        string fullName = document.Name;
        return new Dictionary<string, object?>
        {
            ["name"] = Path.GetFileName(fullName),
            ["full_name"] = fullName,
            ["is_read_only"] = document.IsReadOnly,
            ["is_named_drawing"] =
                !string.IsNullOrWhiteSpace(document.Database.Filename)
        };
    }

    private static object GetDrawingUnits(Database database) =>
        new Dictionary<string, object?>
        {
            ["insunits"] = UnitName(database.Insunits),
            ["insunits_code"] = (int)database.Insunits,
            ["unitless"] = database.Insunits == UnitsValue.Undefined
        };

    private static object GetCoordinateSystem(Document document)
    {
        Matrix3d ucs = document.Editor.CurrentUserCoordinateSystem;
        Point3d origin = Point3d.Origin.TransformBy(ucs);
        Vector3d xAxis = Vector3d.XAxis.TransformBy(ucs);
        Vector3d yAxis = Vector3d.YAxis.TransformBy(ucs);
        Vector3d zAxis = Vector3d.ZAxis.TransformBy(ucs);

        return new Dictionary<string, object?>
        {
            ["name"] = "current_ucs",
            ["relative_to"] = "world",
            ["origin"] = PointData(origin),
            ["x_axis"] = VectorData(xAxis),
            ["y_axis"] = VectorData(yAxis),
            ["z_axis"] = VectorData(zAxis),
            ["matrix"] = ucs.ToArray()
        };
    }

    private static object GetDrawingExtents(
        Database database,
        Transaction transaction)
    {
        (bool available, Extents3d extents, int entityCount) =
            CalculateModelSpaceExtents(database, transaction);

        return new Dictionary<string, object?>
        {
            ["available"] = available,
            ["minimum"] = available ? PointData(extents.MinPoint) : null,
            ["maximum"] = available ? PointData(extents.MaxPoint) : null,
            ["entity_count"] = entityCount,
            ["space"] = "model",
            ["coordinate_system"] = "world",
            ["units"] = UnitName(database.Insunits)
        };
    }

    private static object GetLayers(
        Database database,
        Transaction transaction,
        int limit,
        ICollection<string> warnings)
    {
        LayerTable layerTable = (LayerTable)transaction.GetObject(
            database.LayerTableId,
            OpenMode.ForRead);
        List<Dictionary<string, object?>> layers = [];
        foreach (ObjectId layerId in layerTable)
        {
            LayerTableRecord layer = (LayerTableRecord)transaction.GetObject(
                layerId,
                OpenMode.ForRead);
            layers.Add(new Dictionary<string, object?>
            {
                ["name"] = layer.Name,
                ["is_current"] = layerId == database.Clayer,
                ["is_off"] = layer.IsOff,
                ["is_frozen"] = layer.IsFrozen,
                ["is_locked"] = layer.IsLocked,
                ["is_plottable"] = layer.IsPlottable,
                ["color_index"] = layer.Color.ColorIndex
            });
        }

        layers.Sort((left, right) => string.Compare(
            (string?)left["name"],
            (string?)right["name"],
            StringComparison.OrdinalIgnoreCase));
        int total = layers.Count;
        if (total > limit)
        {
            warnings.Add($"Layer results were limited to {limit} of {total}.");
        }

        return new Dictionary<string, object?>
        {
            ["layers"] = layers.Take(limit).ToArray(),
            ["returned_count"] = Math.Min(total, limit),
            ["total_count"] = total,
            ["truncated"] = total > limit
        };
    }

    private static object GetSelectedEntities(
        Document document,
        Transaction transaction,
        int limit,
        ICollection<string> warnings)
    {
        Autodesk.AutoCAD.EditorInput.PromptSelectionResult selection =
            document.Editor.SelectImplied();
        ObjectId[] objectIds =
            selection.Status == Autodesk.AutoCAD.EditorInput.PromptStatus.OK
                ? selection.Value.GetObjectIds()
                : [];

        return EntityCollectionData(
            objectIds,
            transaction,
            limit,
            warnings,
            "selected");
    }

    private static object GetEntitiesInWindow(
        Database database,
        Transaction transaction,
        Point3D minimum,
        Point3D maximum,
        int limit,
        ICollection<string> warnings)
    {
        Point3d minimumPoint = new(minimum.X, minimum.Y, minimum.Z);
        Point3d maximumPoint = new(maximum.X, maximum.Y, maximum.Z);
        List<ObjectId> matches = [];

        foreach (ObjectId objectId in GetModelSpace(database, transaction))
        {
            if (transaction.GetObject(objectId, OpenMode.ForRead) is not Entity entity)
            {
                continue;
            }

            try
            {
                Extents3d extents = entity.GeometricExtents;
                if (Intersects(extents, minimumPoint, maximumPoint))
                {
                    matches.Add(objectId);
                }
            }
            catch (RuntimeException)
            {
                // Some non-graphical or invalid entities do not expose extents.
            }
        }

        Dictionary<string, object?> data = (Dictionary<string, object?>)
            EntityCollectionData(
                matches,
                transaction,
                limit,
                warnings,
                "window");
        data["window_min"] = PointData(minimumPoint);
        data["window_max"] = PointData(maximumPoint);
        data["coordinate_system"] = "world";
        data["match_mode"] = "geometric_extents_intersection";
        return data;
    }

    private static object GetEntityProperties(
        Database database,
        Transaction transaction,
        string objectId)
    {
        Handle handle = ParseHandle(objectId);
        ObjectId databaseId;
        try
        {
            databaseId = database.GetObjectId(false, handle, 0);
        }
        catch (RuntimeException exception)
        {
            throw new CadRequestException(
                "ENTITY_NOT_FOUND",
                $"No entity with handle '{objectId}' was found: {exception.Message}");
        }

        if (databaseId.IsNull ||
            transaction.GetObject(databaseId, OpenMode.ForRead) is not Entity entity)
        {
            throw new CadRequestException(
                "ENTITY_NOT_FOUND",
                $"No entity with handle '{objectId}' was found.");
        }

        Dictionary<string, object?> properties = EntitySummary(entity);
        properties["geometry"] = GeometryData(entity);
        properties["linetype"] = entity.Linetype;
        properties["lineweight"] = entity.LineWeight.ToString();
        properties["visible"] = entity.Visible;
        return new Dictionary<string, object?>
        {
            ["entity"] = properties
        };
    }

    private static object FindEntitiesByImportId(
        Database database,
        Transaction transaction,
        string importId,
        int limit,
        ICollection<string> warnings)
    {
        List<ObjectId> matches = [];
        foreach (ObjectId objectId in GetModelSpace(database, transaction))
        {
            if (transaction.GetObject(objectId, OpenMode.ForRead) is not Entity entity)
            {
                continue;
            }

            Dictionary<string, string> provenance = GetProvenance(entity);
            if (provenance.TryGetValue("import_id", out string? entityImportId) &&
                string.Equals(entityImportId, importId, StringComparison.Ordinal))
            {
                matches.Add(objectId);
            }
        }

        Dictionary<string, object?> data = (Dictionary<string, object?>)
            EntityCollectionData(
                matches,
                transaction,
                limit,
                warnings,
                "import_id");
        data["target_import_id"] = importId;
        return data;
    }

    private static object EntityCollectionData(
        IEnumerable<ObjectId> objectIds,
        Transaction transaction,
        int limit,
        ICollection<string> warnings,
        string source)
    {
        List<Dictionary<string, object?>> entities = [];
        int total = 0;
        foreach (ObjectId objectId in objectIds)
        {
            total++;
            if (entities.Count >= limit)
            {
                continue;
            }

            if (transaction.GetObject(objectId, OpenMode.ForRead) is Entity entity)
            {
                entities.Add(EntitySummary(entity));
            }
        }

        if (total > limit)
        {
            warnings.Add($"Entity results were limited to {limit} of {total}.");
        }

        return new Dictionary<string, object?>
        {
            ["source"] = source,
            ["entities"] = entities,
            ["returned_count"] = entities.Count,
            ["total_count"] = total,
            ["truncated"] = total > limit
        };
    }

    private static Dictionary<string, object?> EntitySummary(Entity entity)
    {
        Dictionary<string, string> provenance = GetProvenance(entity);
        Dictionary<string, object?> summary = new()
        {
            ["object_id"] = entity.Handle.ToString(),
            ["object_type"] = entity.GetRXClass().DxfName,
            ["layer"] = entity.Layer,
            ["color_index"] = entity.ColorIndex,
            ["provenance"] = provenance.Count == 0 ? null : provenance
        };

        try
        {
            Extents3d extents = entity.GeometricExtents;
            summary["extents"] = new Dictionary<string, object?>
            {
                ["minimum"] = PointData(extents.MinPoint),
                ["maximum"] = PointData(extents.MaxPoint)
            };
        }
        catch (RuntimeException)
        {
            summary["extents"] = null;
        }

        return summary;
    }

    private static object GeometryData(Entity entity) =>
        entity switch
        {
            Line line => new Dictionary<string, object?>
            {
                ["start"] = PointData(line.StartPoint),
                ["end"] = PointData(line.EndPoint),
                ["length"] = line.Length
            },
            Circle circle => new Dictionary<string, object?>
            {
                ["center"] = PointData(circle.Center),
                ["radius"] = circle.Radius
            },
            Arc arc => new Dictionary<string, object?>
            {
                ["center"] = PointData(arc.Center),
                ["radius"] = arc.Radius,
                ["start_angle_radians"] = arc.StartAngle,
                ["end_angle_radians"] = arc.EndAngle
            },
            Polyline polyline => PolylineData(polyline),
            DBText text => new Dictionary<string, object?>
            {
                ["text"] = text.TextString,
                ["position"] = PointData(text.Position),
                ["height"] = text.Height
            },
            MText text => new Dictionary<string, object?>
            {
                ["text"] = text.Contents,
                ["position"] = PointData(text.Location),
                ["height"] = text.TextHeight
            },
            Curve curve => new Dictionary<string, object?>
            {
                ["closed"] = curve.Closed
            },
            _ => new Dictionary<string, object?>()
        };

    private static object PolylineData(Polyline polyline)
    {
        int returnedVertices = Math.Min(
            polyline.NumberOfVertices,
            MaximumPolylineVertices);
        List<Dictionary<string, double>> vertices = [];
        for (int index = 0; index < returnedVertices; index++)
        {
            vertices.Add(PointData(polyline.GetPoint3dAt(index)));
        }

        return new Dictionary<string, object?>
        {
            ["closed"] = polyline.Closed,
            ["vertex_count"] = polyline.NumberOfVertices,
            ["vertices"] = vertices,
            ["vertices_truncated"] =
                polyline.NumberOfVertices > MaximumPolylineVertices
        };
    }

    private static Dictionary<string, string> GetProvenance(Entity entity)
    {
        Dictionary<string, string> values = [];
        using ResultBuffer? xdata =
            entity.GetXDataForApplication(ProvenanceApplicationName);
        if (xdata == null)
        {
            return values;
        }

        TypedValue[] entries = xdata.AsArray();
        for (int index = 1; index + 1 < entries.Length; index += 2)
        {
            if (entries[index].Value is string key &&
                entries[index + 1].Value is string value)
            {
                values[key] = value;
            }
        }

        return values;
    }

    private static BlockTableRecord GetModelSpace(
        Database database,
        Transaction transaction)
    {
        BlockTable blockTable = (BlockTable)transaction.GetObject(
            database.BlockTableId,
            OpenMode.ForRead);
        return (BlockTableRecord)transaction.GetObject(
            blockTable[BlockTableRecord.ModelSpace],
            OpenMode.ForRead);
    }

    private static (bool Available, Extents3d Extents, int EntityCount)
        CalculateModelSpaceExtents(
            Database database,
            Transaction transaction)
    {
        bool available = false;
        Extents3d aggregate = default;
        int entityCount = 0;
        foreach (ObjectId objectId in GetModelSpace(database, transaction))
        {
            if (transaction.GetObject(objectId, OpenMode.ForRead) is not Entity entity)
            {
                continue;
            }

            entityCount++;
            try
            {
                Extents3d extents = entity.GeometricExtents;
                if (!available)
                {
                    aggregate = extents;
                    available = true;
                }
                else
                {
                    aggregate.AddExtents(extents);
                }
            }
            catch (RuntimeException)
            {
                // Keep the entity count, but omit invalid extents.
            }
        }

        return (available, aggregate, entityCount);
    }

    private static bool Intersects(
        Extents3d extents,
        Point3d minimum,
        Point3d maximum) =>
        extents.MinPoint.X <= maximum.X &&
        extents.MaxPoint.X >= minimum.X &&
        extents.MinPoint.Y <= maximum.Y &&
        extents.MaxPoint.Y >= minimum.Y &&
        extents.MinPoint.Z <= maximum.Z &&
        extents.MaxPoint.Z >= minimum.Z;

    private static Handle ParseHandle(string? value)
    {
        if (string.IsNullOrWhiteSpace(value) ||
            !long.TryParse(
                value,
                NumberStyles.AllowHexSpecifier,
                CultureInfo.InvariantCulture,
                out long numericHandle))
        {
            throw new CadRequestException(
                "INVALID_OBJECT_ID",
                "parameters.object_id must be a hexadecimal AutoCAD handle.");
        }

        return new Handle(numericHandle);
    }

    private static Dictionary<string, double> PointData(Point3d point) =>
        new()
        {
            ["x"] = point.X,
            ["y"] = point.Y,
            ["z"] = point.Z
        };

    private static Dictionary<string, double> VectorData(Vector3d vector) =>
        new()
        {
            ["x"] = vector.X,
            ["y"] = vector.Y,
            ["z"] = vector.Z
        };

    private static string UnitName(UnitsValue units) =>
        units switch
        {
            UnitsValue.Undefined => "unitless",
            UnitsValue.Inches => "inches",
            UnitsValue.Feet => "feet",
            UnitsValue.Millimeters => "millimeters",
            UnitsValue.Centimeters => "centimeters",
            UnitsValue.Meters => "meters",
            _ => units.ToString().ToLowerInvariant()
        };

    private static string ReadSuccessMessage(string operation) =>
        operation switch
        {
            "get_drawing_context" => "Drawing context retrieved.",
            "get_active_document" => "Active document retrieved.",
            "get_drawing_units" => "Drawing units retrieved.",
            "get_current_coordinate_system" => "Coordinate system retrieved.",
            "get_drawing_extents" => "Drawing extents retrieved.",
            "list_layers" => "Layers retrieved.",
            "get_selected_entities" => "Selected entities retrieved.",
            "get_entities_in_window" => "Window entities retrieved.",
            "get_entity_properties" => "Entity properties retrieved.",
            "find_entities_by_import_id" => "Import entities retrieved.",
            _ => "Read operation completed."
        };
}
