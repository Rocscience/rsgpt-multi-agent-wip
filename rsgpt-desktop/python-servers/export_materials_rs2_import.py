import os, json, random, shutil, socket
from pathlib import Path

from rs3.RS3Modeler import RS3Modeler
from rs3._client import Client
from rs3.Model import Model

from rs3.properties.PropertyEnums import ConstitutiveModelTypes, MaterialElasticityTypes

# =====================
# 1) Connect-or-launch
# =====================

TUTORIAL_FINAL_PATH = r"C:\Users\Public\Documents\Rocscience\RS3 Examples\Tutorials\Import RS2 Project to RS3\Materials and Staging - final.rs3v3"

# Write outputs beside the input model.
OUTPUT_JSON = str(Path(TUTORIAL_FINAL_PATH).with_suffix("")) + "_material_export.json"
OUTPUT_MODEL_COPY = str(Path(TUTORIAL_FINAL_PATH).with_suffix("")) + "_export_copy.rs3v3"

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
    print(f"Reattached to open model on port {PORT}", flush=True)
else:
    PORT = random.randint(49152, 65535)
    RS3Modeler.startApplication(PORT)
    modeler = RS3Modeler(PORT)

    # Work on a copy to avoid mutating the tutorial original.
    try:
        shutil.copy(TUTORIAL_FINAL_PATH, OUTPUT_MODEL_COPY)
    except shutil.SameFileError:
        pass

    model = modeler.openFile(OUTPUT_MODEL_COPY)

    SESSION_FILE.write_text(
        json.dumps({"port": PORT, "project_id": model._projectId, "model_path": OUTPUT_MODEL_COPY})
    )
    print(f"Launched RS3 on port {PORT}, opened {OUTPUT_MODEL_COPY}", flush=True)


# =====================
# 2) Safe material export
# =====================

def _safe_get(fn):
    """Call a getter that can fail if a property group is inactive.

    We intentionally catch only AttributeError (missing getter) and generic
    Exception (inactive stiffness types can throw). Returned None means
    "not available / not active".
    """
    try:
        return fn()
    except (AttributeError, Exception):
        return None


def _export_strength_params(mat, constitutive_type: ConstitutiveModelTypes):
    cm = mat.ConstitutiveModel

    if constitutive_type == ConstitutiveModelTypes.MOHR_COULOMB:
        mc = cm.MohrCoulomb
        return {
            "cohesion": _safe_get(mc.getCohesion),
            "friction_angle": _safe_get(mc.getFrictionAngle),
            "dilation_angle": _safe_get(mc.getDilationAngle),
        }

    if constitutive_type == ConstitutiveModelTypes.HOEK_BROWN:
        hb = cm.HoekBrown
        # Hoek-Brown does not have c/phi/dilation.
        return hb.getProperties()

    if constitutive_type == ConstitutiveModelTypes.GENERALIZED_HOEK_BROWN:
        ghb = cm.GeneralizedHoekBrown
        return ghb.getProperties()

    if constitutive_type == ConstitutiveModelTypes.DRUCKER_PRAGER:
        dp = cm.DruckerPrager
        return dp.getProperties()

    if constitutive_type == ConstitutiveModelTypes.CAM_CLAY:
        cc = cm.CamClay
        return cc.getProperties()

    # Fallback: best-effort empty (we only guarantee c/phi/dilation when active).
    return {}


def _export_elastic(mat, constitutive_type: ConstitutiveModelTypes):
    cm = mat.ConstitutiveModel
    model_obj = None

    if constitutive_type == ConstitutiveModelTypes.MOHR_COULOMB:
        model_obj = cm.MohrCoulomb
    elif constitutive_type == ConstitutiveModelTypes.HOEK_BROWN:
        model_obj = cm.HoekBrown
    elif constitutive_type == ConstitutiveModelTypes.GENERALIZED_HOEK_BROWN:
        model_obj = cm.GeneralizedHoekBrown
    elif constitutive_type == ConstitutiveModelTypes.DRUCKER_PRAGER:
        model_obj = cm.DruckerPrager
    elif constitutive_type == ConstitutiveModelTypes.CAM_CLAY:
        model_obj = cm.CamClay

    if model_obj is None:
        return {"elastic_type": None, "youngs_modulus": None, "poissons_ratio": None}

    elastic_type = _safe_get(model_obj.getElasticType)

    out = {
        "elastic_type": elastic_type.name if elastic_type is not None else None,
        "youngs_modulus": None,
        "poissons_ratio": None,
    }

    if elastic_type == MaterialElasticityTypes.LINEAR_ISOTROPIC:
        li = model_obj.LinearIsotropicStiffness
        out["youngs_modulus"] = _safe_get(li.getYoungsModulus)
        out["poissons_ratio"] = _safe_get(li.getPoissonsRatio)
    elif elastic_type == MaterialElasticityTypes.TRANSVERSELY_ISOTROPIC:
        ti = model_obj.TransverselyIsotropicStiffness
        # no single E/v pair; keep a representative E and v and also include full dict
        out["youngs_modulus"] = _safe_get(ti.getYoungsModulusE1AndE3)
        out["poissons_ratio"] = _safe_get(ti.getPoissonsRatioV12)
        out["elastic_properties"] = ti.getProperties()
    elif elastic_type == MaterialElasticityTypes.ORTHOTROPIC:
        ortho = model_obj.OrthotropicStiffness
        out["youngs_modulus"] = _safe_get(ortho.getYoungsModulusE1)
        out["poissons_ratio"] = _safe_get(ortho.getPoissonsRatioV12)
        out["elastic_properties"] = ortho.getProperties()

    return out


materials = model.getAllMaterialProperties()
stage_names = model.ProjectSettings.Stages.getDefinedStageNames()
external_vols = model.getAllExternalVolumes()

# Map: stageNumber (1-based) -> stageName
stage_map = {i + 1: stage_names[i] for i in range(len(stage_names))}

export = {
    "source_model": TUTORIAL_FINAL_PATH,
    "opened_model": _sess["model_path"] if (_sess and _port_alive(_sess.get("port"))) else OUTPUT_MODEL_COPY,
    "output_json": OUTPUT_JSON,
    "stages": [{"stage_number": sn, "name": nm} for sn, nm in stage_map.items()],
    "materials": [],
    "assignments_by_stage": {str(sn): {} for sn in stage_map.keys()},
}

# Precompute assignment: stage -> material -> [vol names]
for sn in stage_map.keys():
    for v in external_vols:
        vname = v.getName()
        mname = v.getAppliedMaterialProperty(sn)
        export["assignments_by_stage"][str(sn)].setdefault(mname, []).append(vname)

for mat in materials:
    name = mat.getMaterialName()
    constitutive_type = mat.ConstitutiveModel.getConstitutiveModel()

    entry = {
        "name": name,
        "constitutive_model": constitutive_type.name,
        "unit_weight": _safe_get(mat.InitialConditions.getUnitWeight),
        "elastic": _export_elastic(mat, constitutive_type),
        "strength": _export_strength_params(mat, constitutive_type),
    }
    export["materials"].append(entry)

Path(OUTPUT_JSON).write_text(json.dumps(export, indent=2))

# Console display: material table + stage assignments
print("\nMATERIAL PROPERTIES", flush=True)
print("name\tmodel\tE\tv\tunit_wt\tcohesion\tphi\tdilation", flush=True)
for m in export["materials"]:
    e = m["elastic"].get("youngs_modulus")
    v = m["elastic"].get("poissons_ratio")
    uw = m.get("unit_weight")
    s = m.get("strength", {})
    c = s.get("cohesion")
    phi = s.get("friction_angle")
    dil = s.get("dilation_angle")
    print(
        f"{m['name']}\t{m['constitutive_model']}\t{e}\t{v}\t{uw}\t{c}\t{phi}\t{dil}",
        flush=True,
    )

print("\nSTAGE ASSIGNMENTS (External Volumes -> Materials)", flush=True)
for sn, nm in stage_map.items():
    print(f"Stage {sn}: {nm}", flush=True)
    stage_assign = export["assignments_by_stage"][str(sn)]
    for mat_name in sorted(stage_assign.keys()):
        vols = stage_assign[mat_name]
        print(f"  {mat_name}: {', '.join(vols)}", flush=True)

print(f"\nWROTE_JSON: {OUTPUT_JSON}", flush=True)
