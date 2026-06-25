import os, json, random, shutil, socket
from pathlib import Path

from rs3.RS3Modeler import RS3Modeler
from rs3._client import Client
from rs3.Model import Model

SESSION_FILE = Path(__file__).resolve().parent / ".rs3_session.json"

TUTORIAL_FINAL_PATH = r"C:\Users\Public\Documents\Rocscience\RS3 Examples\Tutorials\Import RS2 Project to RS3\Materials and Staging - final.rs3v3"
OUTPUT_COPY_PATH = str((Path(__file__).resolve().parent / "Materials_and_Staging_final__export_copy.rs3v3").resolve())
EXPORT_JSON_PATH = str((Path(__file__).resolve().parent / "Materials_and_Staging_final__export.json").resolve())


def _port_alive(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=0.5):
            return True
    except OSError:
        return False


def _safe_get(obj, method_name: str):
    m = getattr(obj, method_name, None)
    if callable(m):
        return m()
    return None


def _safe_get_properties(obj):
    m = getattr(obj, "getProperties", None)
    if callable(m):
        return m()
    return {}


_sess = None
if SESSION_FILE.exists():
    try:
        _sess = json.loads(SESSION_FILE.read_text())
    except (OSError, ValueError):
        _sess = None

if _sess and _port_alive(_sess.get("port")):
    PORT = int(_sess["port"])
    model = Model(Client(PORT), _sess["project_id"])
    active_model_path = _sess.get("model_path")
    print(f"Reattached to open model on port {PORT}", flush=True)
else:
    PORT = random.randint(49152, 65535)
    RS3Modeler.startApplication(PORT)
    modeler = RS3Modeler(PORT)

    shutil.copy(TUTORIAL_FINAL_PATH, OUTPUT_COPY_PATH)
    model = modeler.openFile(OUTPUT_COPY_PATH)

    SESSION_FILE.write_text(
        json.dumps(
            {
                "port": PORT,
                "project_id": model._projectId,
                "model_path": OUTPUT_COPY_PATH,
            }
        )
    )
    active_model_path = OUTPUT_COPY_PATH
    print(f"Launched RS3 on port {PORT}, opened {OUTPUT_COPY_PATH}", flush=True)

# ----------------------------
# Export material properties
# ----------------------------
materials_payload = []
all_materials = model.getAllMaterialProperties()
for mat in all_materials:
    name = mat.getMaterialName()
    color = _safe_get(mat, "getMaterialColor")

    ic = getattr(mat, "InitialConditions", None)
    unit_weight = _safe_get(ic, "getUnitWeight") if ic else None

    cm = getattr(mat, "ConstitutiveModel", None)
    constitutive_model_type = _safe_get(cm, "getConstitutiveModel") if cm else None

    cm_payload = {"constitutive_model": str(constitutive_model_type) if constitutive_model_type is not None else None}

    # Try common constitutive model sub-objects; collect their getProperties() output.
    if cm:
        for sub_name in (
            "MohrCoulomb",
            "HoekBrown",
            "Elastic",
            "CamClay",
            "HardeningSoil",
            "JointedRock",
            "BartonBandis",
            "BoundingSurfacePlasticity",
            "BarcelonaBasic",
            "AnisotropicLinear",
        ):
            sub = getattr(cm, sub_name, None)
            if sub is None:
                continue

            sub_props = _safe_get_properties(sub)
            sub_payload = {"properties": sub_props}

            # Stiffness blocks commonly hang off MohrCoulomb etc.
            for stiff_name in (
                "LinearIsotropicStiffness",
                "NonLinearHyperbolicStiffness",
                "OrthotropicStiffness",
                "TransverselyIsotropicStiffness",
            ):
                stiff = getattr(sub, stiff_name, None)
                if stiff is None:
                    continue
                stiff_payload = {
                    "youngs_modulus": _safe_get(stiff, "getYoungsModulus"),
                    "poissons_ratio": _safe_get(stiff, "getPoissonsRatio"),
                    "properties": _safe_get_properties(stiff),
                }
                sub_payload[stiff_name] = stiff_payload

            cm_payload[sub_name] = sub_payload

    # Convenience fields requested by user (best-effort)
    e_val = None
    nu_val = None
    c_val = None
    phi_val = None
    dil_val = None

    mc = getattr(getattr(mat, "ConstitutiveModel", None), "MohrCoulomb", None)
    if mc is not None:
        try:
            mc_props = mc.getProperties()
        except TypeError:
            mc_props = {}
        c_val = mc_props.get("Cohesion")
        phi_val = mc_props.get("FrictionAngle")
        dil_val = mc_props.get("DilationAngle")
        li = getattr(mc, "LinearIsotropicStiffness", None)
        if li is not None:
            e_val = _safe_get(li, "getYoungsModulus")
            nu_val = _safe_get(li, "getPoissonsRatio")

    materials_payload.append(
        {
            "name": name,
            "color_rgba": color,
            "unit_weight": unit_weight,
            "E": e_val,
            "nu": nu_val,
            "c": c_val,
            "phi": phi_val,
            "dilation_angle": dil_val,
            "constitutive_model": cm_payload,
        }
    )

# ----------------------------
# Export stage names and volume-material assignments
# ----------------------------
stages_obj = model.ProjectSettings.Stages
stage_names = []
if stages_obj is not None:
    stage_names = stages_obj.getDefinedStageNames()

external_volumes = model.getAllExternalVolumes()
assignments_by_stage = []

for stage_num, stage_name in enumerate(stage_names, start=1):
    stage_assignment = {"stage_num": stage_num, "stage_name": stage_name, "assignments": []}
    for vol in external_volumes:
        vol_name = vol.getName()
        role = str(vol.getRole())
        mat_name = vol.getAppliedMaterialProperty(stage_num)
        stage_assignment["assignments"].append(
            {
                "external_volume": vol_name,
                "role": role,
                "material": mat_name,
            }
        )
    assignments_by_stage.append(stage_assignment)

# Inverted summary: per stage -> per material -> list of volumes
summary_by_stage_material = []
for stage in assignments_by_stage:
    inv = {}
    for a in stage["assignments"]:
        inv.setdefault(a["material"], []).append(a["external_volume"])
    summary_by_stage_material.append(
        {
            "stage_num": stage["stage_num"],
            "stage_name": stage["stage_name"],
            "materials": [
                {"material": m, "external_volumes": sorted(vs)}
                for m, vs in sorted(inv.items(), key=lambda kv: str(kv[0]))
            ],
        }
    )

payload = {
    "source_model": active_model_path,
    "materials": materials_payload,
    "stages": [{"stage_num": i + 1, "stage_name": n} for i, n in enumerate(stage_names)],
    "external_volume_assignments_by_stage": assignments_by_stage,
    "summary_by_stage_material": summary_by_stage_material,
}

Path(EXPORT_JSON_PATH).write_text(json.dumps(payload, indent=2))
print(f"WROTE_JSON: {EXPORT_JSON_PATH}", flush=True)
print("SUMMARY:")
print(json.dumps({"n_materials": len(materials_payload), "n_external_volumes": len(external_volumes), "n_stages": len(stage_names)}, indent=2), flush=True)
