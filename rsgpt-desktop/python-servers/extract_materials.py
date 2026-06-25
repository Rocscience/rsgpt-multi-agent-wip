import json, os, random, shutil, socket
from pathlib import Path

import grpc
from rs3.RS3Modeler import RS3Modeler
from rs3._client import Client
from rs3.Model import Model

# User-provided model path
TUTORIAL_FINAL_PATH = r"C:\Users\Public\Documents\Rocscience\RS3 Examples\Tutorials\Embankment Consolidation-no wick drain\Embankment Consolidation-no wick drain.rs3v3"

# Save a copy so we don't mutate the original tutorial file
OUTPUT_PATH = str(Path(__file__).resolve().parent / "Embankment_Consolidation_no_wick_drain__materials_extract.rs3v3")

SESSION_FILE = Path(__file__).resolve().parent / ".rs3_session.json"


def _port_alive(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=0.5):
            return True
    except OSError:
        return False


_sess = None
if SESSION_FILE.exists():
    try:
        _sess = json.loads(SESSION_FILE.read_text())
    except (OSError, ValueError):
        _sess = None

if _sess and _port_alive(_sess.get("port")):
    PORT = int(_sess["port"])
    model = Model(Client(PORT), _sess["project_id"])
    active_path = _sess.get("model_path")
    print(f"Reattached to open model on port {PORT} (model_path={active_path})", flush=True)
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


def _extract_material_row(mat):
    name = mat.getMaterialName()

    gamma = None
    try:
        gamma = mat.InitialConditions.getUnitWeight()
    except Exception:
        gamma = None

    c = None
    phi = None
    E = None

    # Mohr-Coulomb (most common for soils)
    try:
        mc = mat.ConstitutiveModel.MohrCoulomb
        props = mc.getProperties()
        c = props.get("Cohesion")
        phi = props.get("FrictionAngle")
        E = mc.LinearIsotropicStiffness.getYoungsModulus()
    except Exception:
        # If the model uses a different constitutive model, these values may be N/A.
        pass

    return {
        "name": name,
        "unit_weight": gamma,
        "cohesion": c,
        "friction_angle": phi,
        "youngs_modulus": E,
    }


materials = model.getAllMaterialProperties()
out = [_extract_material_row(m) for m in materials]
print("STATE: " + json.dumps({"materials": out}, indent=2), flush=True)

# Do not close RS3
