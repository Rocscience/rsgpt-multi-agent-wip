import os, json, random, shutil, socket
from pathlib import Path

from rs3.RS3Modeler import RS3Modeler
from rs3._client import Client
from rs3.Model import Model

# --- Input model (use FINAL tutorial file path from rs3_list_tutorials) ---
TUTORIAL_FINAL_PATH = r"C:\Users\Public\Documents\Rocscience\RS3 Examples\Tutorials\Piled Raft Foundation\Piled Raft Foundation.rs3v3"

# Save a copy beside this script when run via rs3_execute_script (scripts dir)
OUTPUT_PATH = str((Path(__file__).resolve().parent / "piled_raft_foundation_extracted.rs3v3").resolve())

SESSION_FILE = Path(__file__).resolve().parent / ".rs3_session.json"


def _port_alive(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=0.5):
            return True
    except OSError:
        return False


def _attach_or_launch():
    sess = None
    if SESSION_FILE.exists():
        try:
            sess = json.loads(SESSION_FILE.read_text())
        except (OSError, ValueError):
            sess = None

    if sess and _port_alive(sess.get("port")):
        port = int(sess["port"])
        model = Model(Client(port), sess["project_id"])
        out_path = sess["model_path"]
        print(f"Reattached to open model on port {port}", flush=True)
        return model, out_path

    port = random.randint(49152, 65535)
    RS3Modeler.startApplication(port)
    modeler = RS3Modeler(port)
    shutil.copy(TUTORIAL_FINAL_PATH, OUTPUT_PATH)
    model = modeler.openFile(OUTPUT_PATH)

    SESSION_FILE.write_text(
        json.dumps({"port": port, "project_id": model._projectId, "model_path": OUTPUT_PATH})
    )
    print(f"Launched RS3 on port {port}, opened {OUTPUT_PATH}", flush=True)
    return model, OUTPUT_PATH


def _safe_get(obj, name, *args, **kwargs):
    fn = getattr(obj, name, None)
    if fn is None:
        return None
    return fn(*args, **kwargs)


def main():
    model, out_path = _attach_or_launch()

    # --- Materials (soil layers usually map to material properties) ---
    materials = []
    mat_objs = model.getAllMaterialProperties()
    for m in mat_objs:
        mat_name = m.getMaterialName()
        ic = m.InitialConditions
        gamma = _safe_get(ic, "getUnitWeight")

        cm = m.ConstitutiveModel
        cm_type = _safe_get(cm, "getConstitutiveModel")

        coh = phi = E = nu = None
        if hasattr(cm, "MohrCoulomb"):
            mc = cm.MohrCoulomb
            props = _safe_get(mc, "getProperties") or {}
            coh = props.get("Cohesion")
            phi = props.get("FrictionAngle")
            li = getattr(mc, "LinearIsotropicStiffness", None)
            if li is not None:
                E = _safe_get(li, "getYoungsModulus")
                nu = _safe_get(li, "getPoissonsRatio")

        materials.append(
            {
                "name": mat_name,
                "unit_weight_gamma": gamma,
                "constitutive_model": str(cm_type),
                "cohesion_or_Su": coh,
                "friction_angle_phi": phi,
                "youngs_modulus_E": E,
                "poissons_ratio_nu": nu,
            }
        )

    # --- Structural properties (liner/raft and pile properties) ---
    liners = []
    for lp in model.getAllLinerProperties():
        lname = lp.getLinerName()
        ltype = _safe_get(lp, "getLinerType")
        std = getattr(lp, "Standard", None)
        std_props = _safe_get(std, "getProperties") if std is not None else None
        liners.append({"name": lname, "liner_type": str(ltype), "standard_properties": std_props})

    piles = []
    for pp in model.getAllPileProperties():
        pname = pp.getPileName()
        # property schema varies by pile type; capture whatever is available
        ptype = _safe_get(pp, "getPileType")
        data = {"name": pname, "pile_type": str(ptype)}
        for attr in ("Standard", "MohrCoulomb", "Elastic", "Pile", "PileMaterial"):
            sub = getattr(pp, attr, None)
            if sub is not None:
                props = _safe_get(sub, "getProperties")
                if props is not None:
                    data[attr] = props
        # common direct getter
        direct_props = _safe_get(pp, "getProperties")
        if direct_props is not None:
            data["properties"] = direct_props
        piles.append(data)

    # --- Geometry-derived info is largely GUI-only; attempt what API exposes ---
    external_vols = []
    for ev in model.getAllExternalVolumes():
        name = _safe_get(ev, "getName")
        # try to capture box corners if available
        geom = {}
        for getter in ("getFirstCorner", "getSecondCorner", "getMinPoint", "getMaxPoint"):
            val = _safe_get(ev, getter)
            if val is not None:
                geom[getter] = val
        external_vols.append({"name": name, "geometry": geom})

    snapshot = {
        "output_model_path": out_path,
        "materials": materials,
        "liner_properties": liners,
        "pile_properties": piles,
        "external_volumes": external_vols,
    }

    print("STATE: " + json.dumps(snapshot, default=str), flush=True)


if __name__ == "__main__":
    main()
