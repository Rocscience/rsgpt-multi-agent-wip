import json, random, shutil, socket
from pathlib import Path

from rs3.RS3Modeler import RS3Modeler
from rs3._client import Client
from rs3.Model import Model

# Target tutorial file (COMPLETED model)
TUTORIAL_FINAL_PATH = r"C:\Users\Public\Documents\Rocscience\RS3 Examples\Tutorials\Import RS2 Project to RS3\Materials and Staging - final.rs3v3"

# Output folder (beside this script when run by the MCP runner)
OUTPUT_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = str(OUTPUT_DIR / "Materials_and_Staging_export.rs3v3")

SESSION_FILE = OUTPUT_DIR / ".rs3_session.json"


def _port_alive(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=0.5):
            return True
    except OSError:
        return False


def _flatten(prefix: str, obj, out: dict):
    if obj is None:
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            _flatten(f"{prefix}.{k}" if prefix else str(k), v, out)
        return
    out[prefix] = obj


_sess = None
if SESSION_FILE.exists():
    try:
        _sess = json.loads(SESSION_FILE.read_text())
    except (OSError, ValueError):
        _sess = None

if _sess and _port_alive(_sess.get("port")):
    PORT = int(_sess["port"])
    model = Model(Client(PORT), _sess["project_id"])
    OUTPUT_PATH = _sess["model_path"]
    print(f"Reattached to open model on port {PORT}", flush=True)
else:
    PORT = random.randint(49152, 65535)
    RS3Modeler.startApplication(PORT)
    modeler = RS3Modeler(PORT)
    shutil.copy(TUTORIAL_FINAL_PATH, OUTPUT_PATH)
    model = modeler.openFile(OUTPUT_PATH)
    SESSION_FILE.write_text(
        json.dumps({"port": PORT, "project_id": model._projectId, "model_path": OUTPUT_PATH})
    )
    print(f"Launched RS3 on port {PORT}, opened {OUTPUT_PATH}", flush=True)


materials_export = []
for mat in model.getAllMaterialProperties():
    mat_name = mat.getMaterialName()

    cm_type = None
    try:
        cm_type = mat.ConstitutiveModel.getConstitutiveModel()
    except Exception:
        cm_type = None

    params = {}

    # Initial conditions (includes UnitWeight)
    if hasattr(mat, "InitialConditions") and hasattr(mat.InitialConditions, "getProperties"):
        _flatten("InitialConditions", mat.InitialConditions.getProperties(), params)

    # Hydraulic
    if hasattr(mat, "Hydraulic") and hasattr(mat.Hydraulic, "getProperties"):
        _flatten("Hydraulic", mat.Hydraulic.getProperties(), params)

    # Datum dependencies
    if hasattr(mat, "Datum") and hasattr(mat.Datum, "getProperties"):
        _flatten("Datum", mat.Datum.getProperties(), params)

    # Constitutive model subtype properties (only flatten the active subtype)
    if cm_type is not None:
        try:
            cm_obj = getattr(mat.ConstitutiveModel, str(cm_type).split(".")[-1], None)
            if cm_obj is not None and hasattr(cm_obj, "getProperties"):
                _flatten(f"ConstitutiveModel.{cm_type}", cm_obj.getProperties(), params)
        except Exception:
            pass

        # Stiffness model subtype (for models like Mohr-Coulomb)
        try:
            if hasattr(mat.ConstitutiveModel, "MohrCoulomb") and hasattr(
                mat.ConstitutiveModel.MohrCoulomb, "getElasticType"
            ):
                elast_type = mat.ConstitutiveModel.MohrCoulomb.getElasticType()
                stiff_group = None
                if elast_type is not None:
                    stiff_group = getattr(mat.ConstitutiveModel.MohrCoulomb, str(elast_type).split(".")[-1], None)
                if stiff_group is not None and hasattr(stiff_group, "getProperties"):
                    _flatten(f"ConstitutiveModel.MohrCoulomb.{elast_type}", stiff_group.getProperties(), params)
        except Exception:
            pass

    materials_export.append(
        {
            "name": mat_name,
            "constitutive_model": str(cm_type) if cm_type is not None else None,
            "parameters": params,
        }
    )


# Material assignments per volume, per stage
assignments = []
try:
    stages = model.getAllStages()
    stage_numbers = [s.getNumber() for s in stages]
except Exception:
    stage_numbers = [1]

for vol in model.getAllExternalVolumes():
    vol_name = None
    if hasattr(vol, "getName"):
        try:
            vol_name = vol.getName()
        except Exception:
            vol_name = None

    by_stage = {}
    for st in stage_numbers:
        try:
            by_stage[str(st)] = vol.getAppliedMaterialProperty(st)
        except Exception:
            by_stage[str(st)] = None

    assignments.append(
        {
            "external_volume_name": vol_name,
            "applied_material_by_stage": by_stage,
        }
    )


export = {
    "tutorial": "Materials and Staging",
    "opened_model_path": OUTPUT_PATH,
    "source_tutorial_path": TUTORIAL_FINAL_PATH,
    "materials": materials_export,
    "external_volume_material_assignments": assignments,
    "stage_numbers": stage_numbers,
}

json_path = Path(OUTPUT_PATH + "_materials_export.json")
json_path.write_text(json.dumps(export, indent=2))
print(f"WROTE_JSON: {json_path}", flush=True)

model.saveAs(OUTPUT_PATH)
print(f"SAVED_MODEL: {OUTPUT_PATH}", flush=True)
