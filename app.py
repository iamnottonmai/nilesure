import random
from datetime import date, datetime

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="นิลชัวร์ | Fish Traceability",
    page_icon="🐟",
    layout="wide",
)

TILAPIA = "ปลานิล — Nile tilapia"
BLACKCHIN = "ปลาหมอคางดำ — Blackchin tilapia"
UNCLEAR = "Unable to identify"
RESULTS = [TILAPIA, BLACKCHIN, UNCLEAR]

if "lots" not in st.session_state:
    st.session_state.lots = {}

lots = st.session_state.lots


def timestamp():
    return datetime.now().isoformat(timespec="seconds")


def make_record(result, image, reviewer):
    return {
        "prediction": result,
        "photo": image.getvalue() if image else None,
        "screened_at": timestamp(),
        "reviewer": reviewer,
        "model_version": "SIMULATOR — no trained model",
        "confidence": None,
        "demo": True,
    }


def farm_complete(lot):
    return len(lot["farm_checks"]) == len(lot["sample_ids"])


def flagged(record):
    return record["prediction"] != TILAPIA


def lot_on_hold(lot):
    records = [
        *lot["farm_checks"].values(),
        *lot["shop_checks"].values(),
    ]
    return any(flagged(record) for record in records)


def lot_status(lot):
    if lot_on_hold(lot):
        return "On hold — review required"
    if not farm_complete(lot):
        return "Farm screening"
    if lot["arrived"]:
        if len(lot["shop_checks"]) == lot["quantity"]:
            return "Individual screening complete"
        return "Received — individual screening"
    if lot["dispatched"]:
        return "In transit"
    return "Ready for dispatch"


def choose_lot(key):
    if not lots:
        st.info("Create a lot first.")
        return None
    return st.selectbox("Select lot", list(lots), key=key)


def show_record(record):
    if record["photo"]:
        st.image(record["photo"], width=320)
    st.write("**Simulated prediction:**", record["prediction"])
    st.write("**Recorded at:**", record["screened_at"])
    st.write("**Operator:**", record["reviewer"])
    st.caption(
        "No real AI inference was performed. "
        "No confidence score or accuracy claim is available."
    )


def screening_form(lot_id, stage):
    lot = lots[lot_id]
    is_farm = stage == "farm"
    checks = lot["farm_checks"] if is_farm else lot["shop_checks"]
    ids = lot["sample_ids"] if is_farm else lot["fish_ids"]
    remaining = [fish_id for fish_id in ids if fish_id not in checks]

    if not remaining:
        st.success("All required screening records have been entered.")
        return

    st.info(
        "Photograph one whole fish from the side on a clean, flat surface. "
        "Keep its physical ID attached to the correct fish. "
        "Retake blurred or obstructed photos."
    )

    with st.form(f"{stage}_{lot_id}_screen"):
        fish_id = st.selectbox("Fish ID", remaining)
        image = st.file_uploader(
            "Upload fish photograph",
            type=["jpg", "jpeg", "png"],
        )
        result = st.selectbox(
            "SIMULATOR: choose the result to test the workflow",
            RESULTS,
        )
        reviewer = st.text_input("Operator name")
        submitted = st.form_submit_button("Save screening record")

    if submitted:
        if image is None or not reviewer.strip():
            st.error("Upload a photo and enter an operator name.")
            return

        checks[fish_id] = make_record(result, image, reviewer.strip())
        lot["events"].append(
            {
                "time": timestamp(),
                "event": f"{stage.title()} screening: {fish_id} → {result}",
            }
        )
        st.rerun()


st.title("🐟 นิลชัวร์")
st.caption("Farm-to-shop traceability • Know the fish. Know its origin.")
st.warning(
    "DEMONSTRATION ONLY: AI results are manually simulated. "
    "Data and photographs are stored only in this browser session."
)

page = st.sidebar.radio(
    "Workspace",
    [
        "Overview",
        "Create lot",
        "Farm screening",
        "Delivery & shop screening",
        "Customer view",
        "Model transparency",
    ],
)

st.sidebar.info(
    "These workspaces demonstrate roles; they are not access controls. "
    "Production requires authenticated farmer, seller, and reviewer accounts."
)

if page == "Overview":
    st.header("Traceability dashboard")

    a, b, c = st.columns(3)
    a.metric("Lots", len(lots))
    b.metric("Lots on hold", sum(lot_on_hold(x) for x in lots.values()))
    c.metric(
        "Individually screened",
        sum(len(x["shop_checks"]) for x in lots.values()),
    )

    if lots:
        rows = []
        for lot_id, lot in lots.items():
            rows.append(
                {
                    "Lot ID": lot_id,
                    "Farm": lot["farm"],
                    "Shop": lot["shop"],
                    "Fish": lot["quantity"],
                    "Expected arrival": lot["expected"],
                    "Actual arrival": lot["arrived"] or "Not received",
                    "Farm sample": (
                        f'{len(lot["farm_checks"])}/{len(lot["sample_ids"])}'
                    ),
                    "Shop screening": (
                        f'{len(lot["shop_checks"])}/{lot["quantity"]}'
                    ),
                    "Status": lot_status(lot),
                }
            )
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    else:
        st.info("Start by creating a lot such as CSF9238.")

elif page == "Create lot":
    st.header("Create a lot before dispatch")

    with st.form("create_lot"):
        left, right = st.columns(2)
        with left:
            lot_id = st.text_input("Unique Lot ID", "CSF9238")
            farm = st.text_input("Public farm name")
            pond = st.text_input("Pond reference", "P03")
            method = st.text_input("Declared farming method", "Closed pond")
            quantity = st.number_input(
                "Number of fish", min_value=10, max_value=10000, value=100
            )
        with right:
            shop = st.text_input("Destination shop")
            harvest = st.date_input("Harvest date")
            expected = st.date_input("Expected shop arrival")
            delivery_reference = st.text_input("Delivery document reference")
            notes = st.text_area(
                "Public notes",
                placeholder="Do not include private addresses or phone numbers.",
            )

        submitted = st.form_submit_button("Create lot")

    if submitted:
        lot_id = lot_id.strip().upper()
        if not lot_id or not farm.strip() or not shop.strip():
            st.error("Lot ID, farm name, and shop name are required.")
        elif lot_id in lots:
            st.error("This Lot ID already exists.")
        elif expected < harvest:
            st.error("Expected arrival cannot precede harvest.")
        else:
            fish_ids = [
                f"{lot_id}-F{i:03d}" for i in range(1, int(quantity) + 1)
            ]
            lots[lot_id] = {
                "farm": farm.strip(),
                "pond": pond.strip(),
                "method": method.strip(),
                "shop": shop.strip(),
                "quantity": int(quantity),
                "harvest": str(harvest),
                "expected": str(expected),
                "delivery_reference": delivery_reference,
                "notes": notes,
                "fish_ids": fish_ids,
                "sample_ids": sorted(random.sample(fish_ids, 10)),
                "farm_checks": {},
                "shop_checks": {},
                "dispatched": None,
                "arrived": None,
                "received_quantity": None,
                "temperature": None,
                "condition": "",
                "events": [
                    {"time": timestamp(), "event": "Lot created"}
                ],
            }
            st.success(f"Created {lot_id}. Continue to Farm screening.")

elif page == "Farm screening":
    st.header("Farm: randomly sample 10 fish")
    lot_id = choose_lot("farm_lot")

    if lot_id:
        lot = lots[lot_id]
        st.write("**Lot status:**", lot_status(lot))
        st.write("**Randomly selected IDs:**", ", ".join(lot["sample_ids"]))

        st.caption(
            "Assign physical fish IDs before random selection. "
            "Do not substitute easier-to-photograph fish."
        )
        st.info(
            "Sampling does not verify the entire lot. If exactly one fish "
            "in a 100-fish lot is a different species, sampling 10 at random "
            "has only a 10% chance of including it."
        )

        if lot_on_hold(lot):
            st.error(
                "Lot on hold. A suspected species mismatch or unclear result "
                "requires review—not an automatic conclusion that the lot is unsafe."
            )

        screening_form(lot_id, "farm")

        if lot["farm_checks"]:
            st.subheader("Sample records")
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Fish ID": fish_id,
                            "Simulated result": record["prediction"],
                            "Recorded": record["screened_at"],
                        }
                        for fish_id, record in lot["farm_checks"].items()
                    ]
                ),
                hide_index=True,
                use_container_width=True,
            )

        st.caption(
            "This prototype deliberately does not allow hold overrides. "
            "Production needs an authorized expert-review and disposition workflow."
        )

elif page == "Delivery & shop screening":
    st.header("Delivery and individual shop checks")
    lot_id = choose_lot("shop_lot")

    if lot_id:
        lot = lots[lot_id]
        st.write("**Status:**", lot_status(lot))

        if lot_on_hold(lot):
            st.error(
                "Entire lot is on hold. Do not dispatch or offer remaining fish "
                "for sale until an authorized review resolves the issue."
            )

        elif not farm_complete(lot):
            st.info("Complete the 10 farm sample checks before dispatch.")

        elif not lot["dispatched"]:
            if st.button("Confirm dispatch now"):
                lot["dispatched"] = timestamp()
                lot["events"].append(
                    {"time": timestamp(), "event": "Dispatched from farm"}
                )
                st.rerun()

        elif not lot["arrived"]:
            st.write("**Dispatched:**", lot["dispatched"])

            with st.form(f"receive_{lot_id}"):
                arrival = st.date_input("Actual shop arrival", date.today())
                received = st.number_input(
                    "Fish received", min_value=0, value=lot["quantity"]
                )
                temp_text = st.text_input(
                    "Measured receiving temperature in °C (optional)"
                )
                condition = st.text_area("Receiving-condition observations")
                receive = st.form_submit_button("Confirm receipt")

            if receive:
                try:
                    temperature = float(temp_text) if temp_text.strip() else None
                except ValueError:
                    st.error("Enter a numeric temperature or leave it blank.")
                else:
                    if arrival < date.fromisoformat(lot["dispatched"][:10]):
                        st.error("Arrival cannot precede dispatch.")
                    elif arrival > date.today():
                        st.error("Actual arrival cannot be in the future.")
                    elif int(received) != lot["quantity"]:
                        st.error(
                            "Quantity mismatch: reconcile the fish IDs and "
                            "delivery records before continuing. This demo "
                            "supports full-lot receipt only."
                        )
                    else:
                        lot["arrived"] = str(arrival)
                        lot["received_quantity"] = int(received)
                        lot["temperature"] = temperature
                        lot["condition"] = condition
                        lot["events"].append(
                            {"time": timestamp(), "event": "Received by shop"}
                        )
                        st.rerun()

        else:
            st.success(f'Received on {lot["arrived"]}')
            st.write(
                f'Individual checks: {len(lot["shop_checks"])}/{lot["quantity"]}'
            )
            screening_form(lot_id, "shop")

elif page == "Customer view":
    st.header("Customer fish passport")
    st.caption(
        "This previews the page that an individual fish’s QR code would open."
    )

    lot_id = choose_lot("customer_lot")
    if lot_id:
        lot = lots[lot_id]
        fish_id = st.selectbox("Individual Fish ID", lot["fish_ids"])
        record = lot["shop_checks"].get(fish_id)

        st.subheader(fish_id)
        st.write("**Lot ID:**", lot_id)

        if lot_on_hold(lot):
            st.error("LOT ON HOLD — review required. Not available for sale.")
        elif not record:
            st.warning("This fish has not completed individual shop screening.")
        else:
            st.success(
                "Demo screening recorded: predicted tilapia. "
                "This is not a food-safety certification."
            )

        if record:
            show_record(record)

        origin, journey, education = st.tabs(
            ["Origin & handling", "Journey & checks", "Know the difference"]
        )

        with origin:
            st.write("**Declared species:**", TILAPIA)
            st.write("**Farm:**", lot["farm"])
            st.write("**Pond reference:**", lot["pond"])
            st.write("**Farming method, declared by farm:**", lot["method"])
            st.write("**Destination shop:**", lot["shop"])
            st.write("**Harvest date:**", lot["harvest"])
            st.write("**Expected arrival:**", lot["expected"])
            st.write("**Actual arrival:**", lot["arrived"] or "Not received")
            st.write(
                "**Delivery reference:**",
                lot["delivery_reference"] or "Not provided",
            )
            temp = lot["temperature"]
            st.write(
                "**Recorded receiving temperature:**",
                f"{temp}°C" if temp is not None else "Not recorded",
            )
            st.write(
                "**Receiving observations:**",
                lot["condition"] or "Not recorded",
            )
            if lot["notes"]:
                st.write("**Farm notes:**", lot["notes"])
            st.caption(
                "These are operator-entered records, not independently "
                "verified certificates."
            )

        with journey:
            st.write(
                "**Farm sample checks:**",
                f'{len(lot["farm_checks"])}/10 recorded',
            )
            st.write(
                "**Individual shop checks:**",
                f'{len(lot["shop_checks"])}/{lot["quantity"]} recorded',
            )
            st.caption(
                "Farm sample findings apply only to the sampled fish. "
                "Individual shop findings apply to the photographed fish."
            )
            st.dataframe(
                pd.DataFrame(lot["events"]),
                hide_index=True,
                use_container_width=True,
            )

        with education:
            st.subheader("ปลานิล vs ปลาหมอคางดำ")
            st.table(
                pd.DataFrame(
                    [
                        {
                            "Common name": "ปลานิล / Nile tilapia",
                            "Scientific name": "Oreochromis niloticus",
                        },
                        {
                            "Common name": "ปลาหมอคางดำ / Blackchin tilapia",
                            "Scientific name": "Sarotherodon melanotheron",
                        },
                    ]
                )
            )
            st.write(
                "A production comparison guide should show verified side-by-side "
                "photos with expert annotations of the head, chin, body, fins, "
                "and tail."
            )
            st.warning(
                "Visual identification guide pending fisheries-expert review. "
                "Do not identify a fish by a dark chin alone: lighting, age, "
                "and fish condition can affect appearance."
            )
            st.info(
                "Species identity does not establish whether a fish carries "
                "pathogens. Neither a photograph nor a QR code verifies "
                "food safety or proves the pond contains only one species."
            )

elif page == "Model transparency":
    st.header("What the AI numbers mean")

    st.error(
        "No trained model is connected. All predictions in this prototype "
        "are selected manually to demonstrate the workflow."
    )

    metrics = [
        (
            "Individual confidence",
            "A model score for one prediction—not a guarantee that it is correct.",
        ),
        (
            "Test accuracy",
            "Share of evaluated fish classified correctly on a held-out test set.",
        ),
        (
            "Tilapia precision",
            "Among fish predicted as tilapia, the share verified as tilapia.",
        ),
        (
            "Blackchin tilapia recall",
            "Among verified blackchin tilapia, the share detected by the model.",
        ),
        (
            "Unable-to-identify rate",
            "Share of cases where the system withholds a decision.",
        ),
    ]
    st.table(pd.DataFrame(metrics, columns=["Metric", "Meaning"]))

    st.subheader("Required before deploying real AI")
    st.markdown(
        """
- Collect expert-labelled photos from actual farms and shops.
- Keep photographs of the same fish out of different train/test splits.
- Include other species and unsuitable images in evaluation.
- Evaluate false tilapia predictions, not just overall accuracy.
- Calibrate confidence scores and validate the review threshold.
- Publish model version, test date, sample size, and limitations.
- Keep expert review separate from the original model prediction.
"""
    )

st.divider()
st.caption(
    "นิลชัวร์ prototype | Traceability and species screening are not "
    "food-safety certification."
)
