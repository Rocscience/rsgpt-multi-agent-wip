import os, json, random, shutil, socket
from pathlib import Path

import grpc
from rs3.RS3Modeler import RS3Modeler
from rs3._client import Client
from rs3.Model import Model

from rs3.ModelEnums import ComputeType, ComputeStart
from rs3.mesh.MeshEnums import MeshElementType, MeshGradation
from rs3.results.ResultEnums import SolidsDataType

# NOTE:
# - Creating / editing 3D geometry (external box, primitives, Divide All) is GUI-only.
# - Consolidation analysis parameters are not configured here because this tutorial file
#   is already a completed model; this script focuses on running it and extracting results.

TUTORIAL_FINAL_PATH = r"C:\Users\Public\Documents\Rocscience\RS3 Examples\Tutorials\Embankment Consolidation-no wick drain\Embankment Consolidation-no wick drain.rs3v3"
OUTPUT_PATH = str(Path(__file__).resolve().parent / "Embankment_Consolidation_no_wick_drain_output.rs3v3")

SESSION_FILE = Path(__file__).resolve().parent / ".rs3_session.json"

# RS3 precondition messages that mean "a GUI-only step is still needed".
_GUI_PRECONDITION_SIGNATURES = (
    "not ready for meshing",
    "construction role",
    "non-existent or all assigned",
)
GUI_HANDOFFS = []
_BLOCKED = object()


def _port_alive(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=0.5):
            return True
    except OSError:
        return False


def gui_gated(step_label, fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except grpc.RpcError as e:
        detail = (e.details() or str(e))
        if not any(sig in detail.lower() for sig in _GUI_PRECONDITION_SIGNATURES):
            raise
        GUI_HANDOFFS.append({"blocked_step": step_label, "reason": detail})
        print(f"GUI_REQUIRED: {step_label} blocked — {detail}", flush=True)
        return _BLOCKED


def _connect_or_launch():
    sess = None
    if SESSION_FILE.exists():
        try:
            sess = json.loads(SESSION_FILE.read_text())
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
        raise FileNotFoundError(f"Tutorial model not found at: {TUTORIAL_FINAL_PATH}")

    shutil.copy(TUTORIAL_FINAL_PATH, OUTPUT_PATH)
    model = modeler.openFile(OUTPUT_PATH)

    SESSION_FILE.write_text(
        json.dumps({"port": port, "project_id": model._projectId, "model_path": OUTPUT_PATH})
    )
    print(f"Launched RS3 on port {port}, opened {OUTPUT_PATH}", flush=True)
    return model, OUTPUT_PATH


def _max_of_stage(model: Model, stage: int, dtype: SolidsDataType) -> float:
    results = model.Results.getMeshResults(stageNumber=[stage], requiredDataTypes={dtype})
    if not results:
        raise RuntimeError(f"No mesh results returned for stage {stage} and {dtype}")
    nodes = results[0].getMeshNodeResults()
    if not nodes:
        raise RuntimeError("No node results returned")
    return max(float(n.getResult(dtype)) for n in nodes)


def main():
    model, out_path = _connect_or_launch()

    print("Setting mesh settings…", flush=True)
    model.Mesh.setElementType(MeshElementType.MESH_4_NODED_TETRAHEDRA)
    model.Mesh.setMeshGradation(MeshGradation.GRADED)

    model.saveAs(out_path)

    print("Meshing…", flush=True)
    meshed = gui_gated("mesh", model.Mesh.mesh)

    if meshed is not _BLOCKED:
        model.saveAs(out_path)
        print("Computing (ALL, FROM_BEGINNING)…", flush=True)
        computed = gui_gated(
            "compute",
            model.Compute.compute,
            computeType=ComputeType.ALL,
            computeStart=ComputeStart.FROM_BEGINNING,
        )

        if computed is not _BLOCKED:
            success, error_message = computed
            stage_to_query = 1
            try:
                max_disp = _max_of_stage(model, stage_to_query, SolidsDataType.TOTAL_DISPLACEMENT)
            except Exception:
                max_disp = None

            try:
                max_sigma1 = _max_of_stage(model, stage_to_query, SolidsDataType.SIGMA_1_EFFECTIVE)
            except Exception:
                max_sigma1 = None

            try:
                max_total_pwp = _max_of_stage(model, stage_to_query, SolidsDataType.TOTAL_PWP)
            except Exception:
                max_total_pwp = None

            sidecar = {
                "success": bool(success),
                "error_message": error_message,
                "stage_queried": stage_to_query,
                "max_total_displacement": max_disp,
                "max_sigma1_effective": max_sigma1,
                "max_total_pwp": max_total_pwp,
            }
            Path(out_path + "_last_compute.json").write_text(json.dumps(sidecar, indent=2))
            print("COMPUTE_DONE " + json.dumps(sidecar), flush=True)

            # Render nudge: end on stage 1 (only if it exists). If more stages exist, hop.
            try:
                model.setActiveStage(1)
            except Exception:
                pass

    model.saveAs(out_path)
    if GUI_HANDOFFS:
        Path(out_path + "_gui_required.json").write_text(
            json.dumps({"gui_required": True, "model_path": out_path, "blocked_steps": GUI_HANDOFFS}, indent=2)
        )
        print("GUI_REQUIRED: " + json.dumps(GUI_HANDOFFS), flush=True)


if __name__ == "__main__":
    main()
