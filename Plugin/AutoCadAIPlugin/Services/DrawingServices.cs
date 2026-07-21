using AutoCadAIPlugin.Models;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;
using Microsoft.VisualBasic;
using System.Reflection.Metadata;
using System.Transactions;
using Application = Autodesk.AutoCAD.ApplicationServices.Application;

namespace AutoCadAIPlugin.Services;

public class DrawingService
{
    public void CreateLine(CadPayload payload)
    {
        if (payload?.Parameters == null) return;

        Document doc = Application.DocumentManager.MdiActiveDocument;
        Database db = doc.Database;
        LineParams p = payload.Parameters;

        using (Transaction tr = db.TransactionManager.StartTransaction())
        {
            // Layer Table Setup
            LayerTable lt = (LayerTable)tr.GetObject(db.LayerTableId, OpenMode.ForRead);
            if (!lt.Has(p.Layer) && p.CreateLayerIfMissing)
            {
                lt.UpgradeOpen();
                using LayerTableRecord ltr = new() { Name = p.Layer };
                lt.Add(ltr);
                tr.AddNewlyCreatedDBObject(ltr, true);
            }

            // Model Space Access
            BlockTable bt = (BlockTable)tr.GetObject(db.BlockTableId, OpenMode.ForRead);
            BlockTableRecord btr = (BlockTableRecord)tr.GetObject(bt[BlockTableRecord.ModelSpace], OpenMode.ForWrite);

            // Construct Vector Geometry
            Point3d startPt = new(p.Start.X, p.Start.Y, p.Start.Z);
            Point3d endPt = new(p.End.X, p.End.Y, p.End.Z);

            using Line line = new(startPt, endPt);
            if (lt.Has(p.Layer))
            {
                line.Layer = p.Layer;
            }

            btr.AppendEntity(line);
            tr.AddNewlyCreatedDBObject(line, true);

            tr.Commit();
        }
    }
}
