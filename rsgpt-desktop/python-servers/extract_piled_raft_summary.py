import os, json, random, shutil, socket
from pathlib import Path

from rs3.RS3Modeler import RS3Modeler
from rs3._client import Client
from rs3.Model import Model

# -------------------------
# CONFIG
# -------------------------
TUTORIAL_FINAL_PATH = r"C:\Users\Public\Documents\Rocscience\RS3 Examples\Tutorials\Piled Raft Foundation\Piled Raft Foundation.rs3v3"
OUTPUT_PATH = str((Path(__file__).resolve().parent / "piled_raft_foundation_extracted.rs3v3").resolve())

SESSION_FILE = Path(__file__).resolve().parent / ".rs3_session.json"


def _port_alive(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=0.5):
            return True
    except OSError:
        return False


def _connect_or_launch():
    sess = None
    if SESSION_FILE.exists():
        try:
            sess = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            sess = None

    if sess and _port_alive(sess.get("port")):
        port = int(sess["port"])
        model = Model(Client(port), sess["project_id"])
        output_path = sess["model_path"]
        print(f"Reattached to open model on port {port}", flush=True)
        return model, output_path

    port = random.randint(49152, 65535)
    RS3Modeler.startApplication(port)
    modeler = RS3Modeler(port)

    if not os.path.exists(TUTORIAL_FINAL_PATH):
        raise FileNotFoundError(TUTORIAL_FINAL_PATH)

    shutil.copy(TUTORIAL_FINAL_PATH, OUTPUT_PATH)
    model = modeler.openFile(OUTPUT_PATH)
    SESSION_FILE.write_text(
        json.dumps({"port": port, "project_id": model._projectId, "model_path": OUTPUT_PATH}),
        encoding="utf-8",
    )
    print(f"Launched RS3 on port {port}, opened {OUTPUT_PATH}", flush=True)
    return model, OUTPUT_PATH


def _try_call(label, fn):
    try:
        return True, fn()
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def main():
    model, output_path = _connect_or_launch()

    summary = {
        "model_path": output_path,
        "foundation": {},
        "piles": {},
        "soil_layers": [],
        "supports_boundary": {},
        "mesh": {},
    }

    # 1) Foundation layout / raft geometry (best available from API)
    ok, external_vols = _try_call("getAllExternalVolumes", lambda: model.getAllExternalVolumes())
    if ok:
        ev_list = []
        for ev in external_vols:
            ev_list.append(
                {
                    "name": ev.getName(),
                    "role": str(ev.getRole()),
                    "volume": ev.getVolume(),
                    "area": ev.getTotalSurfaceArea(),
                }
            )
        summary["foundation"]["external_volumes"] = ev_list
    else:
        summary["foundation"]["external_volumes_error"] = external_vols

    # 2) Pile properties (NOTE: individual pile-instance coordinates are not exposed)
    ok, piles = _try_call("getAllPileProperties", lambda: model.getAllPileProperties())
    if ok:
        pile_props = []
        for pp in piles:
            p = {
                "name": pp.getPileName(),
                "connection_type": str(pp.getConnectionType()),
                "lining_connection_type": str(pp.getLiningConnectionType()),
                "skin_resistance": str(pp.getSkinResistance()),
                "beam_material": pp.getBeamMaterial(),
                "mc": {
                    "shear_stiffness": pp.MohrCoulomb.getShearStiffness(),
                    "normal_stiffness": pp.MohrCoulomb.getNormalStiffness(),
                    "base_normal_stiffness": pp.MohrCoulomb.getBaseNormalStiffness(),
                    "base_force_resistance": pp.MohrCoulomb.getBaseForceResistance(),
                    "perimeter": pp.MohrCoulomb.getPerimeter(),
                    "cohesion": pp.MohrCoulomb.getCohesion(),
                    "residual_cohesion": pp.MohrCoulomb.getResidualCohesion(),
                    "friction_angle": pp.MohrCoulomb.getFrictionAngle(),
                    "residual_friction_angle": pp.MohrCoulomb.getResidualFrictionAngle(),
                },
            }
            pile_props.append(p)
        summary["piles"]["pile_properties"] = pile_props
    else:
        summary["piles"]["pile_properties_error"] = piles

    # 3) Soil materials (E, nu, gamma) + stack (as far as API allows)
    ok, mats = _try_call("getAllMaterialProperties", lambda: model.getAllMaterialProperties())
    if ok:
        for m in mats:
            name = m.getMaterialName()
            gamma_ok, gamma = _try_call("unit_weight", lambda: m.InitialConditions.getUnitWeight())
            e_ok, E = _try_call(
                "youngs_modulus",
                lambda: m.ConstitutiveModel.MohrCoulomb.LinearIsotropicStiffness.getYoungsModulus(),
            )
            nu_ok, nu = _try_call(
                "poissons_ratio",
                lambda: m.ConstitutiveModel.MohrCoulomb.LinearIsotropicStiffness.getPoissonsRatio(),
            )
            summary["soil_layers"].append(
                {
                    "material": name,
                    "unit_weight_gamma": gamma if gamma_ok else gamma,
                    "youngs_modulus_E": E if e_ok else E,
                    "poissons_ratio_nu": nu if nu_ok else nu,
                }
            )
    else:
        summary["soil_layers_error"] = mats

    # Try to map which material is applied to each external volume at stage 1/2
    if ok and summary.get("foundation", {}).get("external_volumes"):
        stage_map = []
        for ev in model.getAllExternalVolumes():
            stage1_ok, mat1 = _try_call("applied_mat_stage1", lambda ev=ev: ev.getAppliedMaterialProperty(1))
            stage2_ok, mat2 = _try_call("applied_mat_stage2", lambda ev=ev: ev.getAppliedMaterialProperty(2))
            stage_map.append(
                {
                    "external_volume": ev.getName(),
                    "stage1_material": mat1 if stage1_ok else mat1,
                    "stage2_material": mat2 if stage2_ok else mat2,
                }
            )
        summary["foundation"]["external_volume_materials_by_stage"] = stage_map

    # 4) Supports / boundary conditions (auto-restraints status + support properties present)
    r_ok, is_set = _try_call("getIsRestraintsSet", lambda: model.Restraints.getIsRestraintsSet())
    summary["supports_boundary"]["restraints_is_set"] = is_set if r_ok else is_set

    # Liners / beams in model (properties)
    l_ok, liners = _try_call("getAllLinerProperties", lambda: model.getAllLinerProperties())
    if l_ok:
        liners_list = []
        for lp in liners:
            liners_list.append({"name": lp.getLinerName(), "liner_type": str(lp.getLinerType())})
        summary["supports_boundary"]["liner_properties"] = liners_list
    else:
        summary["supports_boundary"]["liner_properties_error"] = liners

    b_ok, beams = _try_call("getAllBeamProperties", lambda: model.getAllBeamProperties())
    if b_ok:
        beam_list = []
        for bp in beams:
            beam_list.append({"name": bp.getBeamName(), "beam_type": str(bp.getBeamType())})
        summary["supports_boundary"]["beam_properties"] = beam_list
    else:
        summary["supports_boundary"]["beam_properties_error"] = beams

    # 5) Mesh info
    et_ok, et = _try_call("getElementType", lambda: model.Mesh.getElementType())
    mg_ok, mg = _try_call("getMeshGradation", lambda: model.Mesh.getMeshGradation())
    summary["mesh"]["element_type"] = et if et_ok else et
    summary["mesh"]["mesh_gradation"] = mg if mg_ok else mg

    model.saveAs(output_path)

    print("STATE: " + json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
