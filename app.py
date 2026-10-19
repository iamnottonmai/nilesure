from datetime import datetime
from hashlib import sha256
from math import comb
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="นิลชัวร์ | Lot Screening",
    page_icon="🐟",
    layout="wide",
)

FISH_DIR = Path(__file__).resolve().parent / "fish"
NILE = "ปลานิล"
BLACK = "ปลาหมอคางดำ"

st.title("🐟 นิลชัวร์")
st.caption("Lot-based traceability and fish screening")

st.warning(
    "PITCH PROTOTYPE — Species results come from filenames, not AI. "
    "All confidence scores are simulated display values. "
    "These selected photos cannot establish real model accuracy."
)

# A different state key avoids conflicts with the earlier prototype.
if "pitch_lots_v2" not in st.session_state:
    st.session_state.pitch_lots_v2 = {}

lots = st.session_state.pitch_lots_v2


def now():
    return datetime.now().isoformat(timespec="seconds")


def load_sets():
    if not FISH_DIR.exists():
        st.error("Create a folder named 'fish' next to app.py.")
        st.stop()

    supported = {".jpg", ".jpeg", ".png", ".webp"}
    files = [
        p for p in FISH_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in supported
    ]

    nile = sorted(
        [p for p in files if p.name.lower().startswith("nile")],
        key=lambda p: p.name,
    )
    black = sorted(
        [p for p in files if p.name.lower().startswith("black")],
        key=lambda p: p.name,
    )

    if len(nile) < 10 or len(black) < 4:
        st.error(
            f"Found {len(nile)} Nile images and {len(black)} blackchin images. "
            "At least 10 Nile images and 4 blackchin images are required."
        )
        st.stop()

    # Prefer different original image groups for the four blackchin slots.
    # This still does not establish that the photos show distinct real fish.
    black_picks = []
    groups = set()

    for path in black:
        group = path.name.split(".rf.")[0]
        if group not in groups:
            black_picks.append(path)
            groups.add(group)
        if len(black_picks) == 4:
            break

    if len(black_picks) < 4:
        for path in black:
            if path not in black_picks:
                black_picks.append(path)
            if len(black_picks) == 4:
                break

    set_one = nile[:10]

    # Rotate the list: reuse across sets, but not within a set.
    set_two = (nile[5:] + nile[:5])[:10]

    six_nile = nile[-6:]
    set_three = [
        six_nile[0], black_picks[0],
        six_nile[1], six_nile[2],
        black_picks[1], six_nile[3],
        black_picks[2], six_nile[4],
        six_nile[5], black_picks[3],
    ]

    return {
        "Set 1 — 10 Nile tilapia": set_one,
        "Set 2 — 10 Nile tilapia": set_two,
        "Set 3 — 6 Nile + 4 blackchin tilapia": set_three,
    }


sets = load_sets()


def demo_score(filename):
    """Stable mock UI score, never a real inference result."""
    value = int(sha256(filename.encode()).hexdigest()[:8], 16)
    return round(95.0 + (value % 450) / 100, 1)


def simulate_screening(paths):
    records = []
    for index, path in enumerate(paths, start=1):
        species = BLACK if path.name.lower().startswith("black") else NILE
        records.append({
            # A temporary image number, NOT a permanent fish ID.
            "sample_photo": index,
            "filename": path.name,
            "species": species,
            "demo_confidence": demo_score(path.name),
        })
    return records


def is_held(lot):
    # Holds persist if ANY screening run has a blackchin result.
    return any(
        row["species"] == BLACK
        for run in lot["runs"]
        for row in run["records"]
    )


def status(lot):
    if is_held(lot):
        return "On hold — species review required"
    if not lot["runs"]:
        return "Awaiting sample screening"
    return "No blackchin flagged in screened samples"


def select_lot(key):
    if not lots:
        st.info("Create a lot first.")
        return None
    return st.selectbox("Lot ID", list(lots.keys()), key=key)


def show_results(run):
    rows = run["records"]
    black_count = sum(row["species"] == BLACK for row in rows)
    nile_count = len(rows) - black_count

    a, b, c = st.columns(3)
    a.metric("Sample photos", len(rows))
    b.metric("Nile tilapia", nile_count)
    c.metric("Blackchin tilapia", black_count)

    if black_count:
        st.error(
            f"DEMO RESULT: Blackchin tilapia detected in "
            f"{black_count}/{len(rows)} sample photos. "
            "Place the lot on hold and request expert inspection."
        )
    else:
        st.success(
            "DEMO RESULT: No blackchin tilapia detected "
            "in these 10 sample photos."
        )
        st.info(
            "This result does not establish that every fish "
            "in the lot is Nile tilapia."
        )

    st.caption(
        f"Stage: {run['stage']} | Recorded: {run['time']} | "
        "Scores below are simulated confidence—not accuracy, "
        "precision, or food-safety ratings."
    )

    for start in range(0, len(rows), 5):
        columns = st.columns(5)
        for column, row in zip(columns, rows[start:start + 5]):
            with column:
                st.image(str(FISH_DIR / row["filename"]), use_column_width=True)
                st.markdown(f"**Photo {row['sample_photo']}**")
                st.write(row["species"])
                st.caption(
                    f"Demo confidence: {row['demo_confidence']:.1f}%"
                )

    with st.expander("Screening details"):
        table = pd.DataFrame([
            {
                "Sample photo": row["sample_photo"],
                "Species — simulated": row["species"],
                "Demo confidence (%)": row["demo_confidence"],
                "Image": row["filename"],
            }
            for row in rows
        ])
        st.dataframe(table, hide_index=True, use_container_width=True)


page = st.sidebar.radio(
    "Navigate",
    [
        "Dashboard",
        "Create lot",
        "Screen sample",
        "Customer lot page",
        "Sampling risk",
    ],
)

st.sidebar.caption(
    "Session-only prototype. No real AI, public QR links, "
    "authentication, or permanent database."
)

if page == "Dashboard":
    st.header("Lot dashboard")

    a, b, c = st.columns(3)
    a.metric("Total lots", len(lots))
    b.metric("Lots on hold", sum(is_held(lot) for lot in lots.values()))
    c.metric(
        "Screening runs",
        sum(len(lot["runs"]) for lot in lots.values()),
    )

    if lots:
        st.dataframe(
            pd.DataFrame([
                {
                    "Lot": lot_id,
                    "Farm": lot["farm"],
                    "Shop": lot["shop"],
                    "Fish in lot": lot["quantity"],
                    "Expected arrival": lot["expected"],
                    "Actual arrival": lot["arrival"] or "Not recorded",
                    "Status": status(lot),
                }
                for lot_id, lot in lots.items()
            ]),
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.info("Start with Create lot, then choose a demonstration image set.")

elif page == "Create lot":
    st.header("Create one ID for the whole lot")
    st.caption("No individual fish IDs are required in this prototype.")

    with st.form("new_lot"):
        left, right = st.columns(2)

        with left:
            lot_id = st.text_input("Lot ID", "CSF9238")
            farm = st.text_input("Farm public name", "Demo Farm")
            pond = st.text_input("Pond reference", "P03")
            quantity = st.number_input(
                "Fish in lot",
                min_value=10,
                max_value=100000,
                value=100,
            )

        with right:
            shop = st.text_input("Destination shop", "Tum's Fish Shop")
            harvest = st.date_input("Harvest date")
            expected = st.date_input("Expected arrival")
            document = st.text_input("Delivery document reference")

        submit = st.form_submit_button("Create lot")

    if submit:
        lot_id = lot_id.strip().upper()
        if not lot_id or not farm.strip() or not shop.strip():
            st.error("Enter a Lot ID, farm, and shop.")
        elif lot_id in lots:
            st.error("This Lot ID already exists.")
        elif expected < harvest:
            st.error("Expected arrival cannot precede harvest.")
        else:
            lots[lot_id] = {
                "farm": farm.strip(),
                "pond": pond.strip(),
                "shop": shop.strip(),
                "quantity": int(quantity),
                "harvest": str(harvest),
                "expected": str(expected),
                "document": document.strip(),
                "arrival": None,
                "runs": [],
            }
            st.success(f"Lot {lot_id} created. Open Screen sample.")

elif page == "Screen sample":
    st.header("Choose a prepared sample")
    st.caption(
        "Selecting a set stands in for uploading 10 sample photographs. "
        "These are curated demonstration sets, not actual random samples."
    )

    lot_id = select_lot("screen_lot")

    if lot_id:
        lot = lots[lot_id]
        st.write("**Lot status:**", status(lot))

        if is_held(lot):
            st.error(
                "This lot is already on hold. Additional clean sample results "
                "will not automatically release it."
            )

        stage = st.radio(
            "Who is checking?",
            ["Farmer — before dispatch", "Seller — at receipt"],
            horizontal=True,
        )

        if stage.startswith("Seller"):
            with st.expander("Record shop arrival"):
                with st.form(f"arrival_{lot_id}"):
                    arrival = st.date_input("Actual arrival date")
                    save_arrival = st.form_submit_button("Save arrival")
                if save_arrival:
                    if str(arrival) < lot["harvest"]:
                        st.error("Arrival cannot precede harvest.")
                    elif arrival > datetime.now().date():
                        st.error("Actual arrival cannot be in the future.")
                    else:
                        lot["arrival"] = str(arrival)
                        st.success("Actual arrival recorded.")

        selected = st.selectbox("Prepared image set", list(sets.keys()))

        with st.expander("Preview selected images"):
            paths = sets[selected]
            for start in range(0, 10, 5):
                columns = st.columns(5)
                for column, path in zip(columns, paths[start:start + 5]):
                    with column:
                        st.image(str(path), use_column_width=True)

        if st.button("Run demonstration screening", type="primary"):
            if stage.startswith("Seller") and not lot["arrival"]:
                st.error("Record actual shop arrival before seller screening.")
            else:
                lot["runs"].append({
                    "stage": stage,
                    "set": selected,
                    "time": now(),
                    "records": simulate_screening(sets[selected]),
                })

        if lot["runs"]:
            st.subheader("Latest screening")
            show_results(lot["runs"][-1])

            if is_held(lot):
                st.warning(
                    "Lot-level action: pause dispatch or sale, retain the "
                    "screening evidence, and ask a qualified reviewer to "
                    "check the suspected fish and investigate the source. "
                    "Hold release is intentionally not implemented here."
                )

elif page == "Customer lot page":
    st.header("Customer traceability page")
    st.caption(
        "Preview of the page a lot-level QR label would open. "
        "All fish from the same lot share this record."
    )

    lot_id = select_lot("public_lot")

    if lot_id:
        lot = lots[lot_id]
        st.subheader(f"Lot {lot_id}")

        if is_held(lot):
            st.error("LOT ON HOLD — species inspection required.")
        elif lot["runs"]:
            st.info(
                "No blackchin flagged in the recorded sample screens. "
                "The particular fish you buy may not have been photographed."
            )
        else:
            st.warning("No sample screening recorded.")

        left, right = st.columns(2)
        with left:
            st.write("**Farm:**", lot["farm"])
            st.write("**Pond reference:**", lot["pond"])
            st.write("**Declared species:**", NILE)
            st.write("**Lot quantity:**", lot["quantity"])
        with right:
            st.write("**Shop:**", lot["shop"])
            st.write("**Harvest:**", lot["harvest"])
            st.write("**Expected arrival:**", lot["expected"])
            st.write("**Actual arrival:**", lot["arrival"] or "Not recorded")

        st.write(
            "**Delivery reference:**",
            lot["document"] or "Not provided",
        )
        st.caption("Origin and delivery fields are entered by the operator.")

        st.subheader("Recorded sample screens")
        if not lot["runs"]:
            st.info("No results yet.")
        for index, run in enumerate(lot["runs"], start=1):
            with st.expander(f"Check {index}: {run['stage']} — {run['time']}"):
                show_results(run)

        st.subheader("Know the difference")
        st.table(pd.DataFrame([
            {
                "Fish": "ปลานิล",
                "English name": "Nile tilapia",
                "Scientific name": "Oreochromis niloticus",
            },
            {
                "Fish": "ปลาหมอคางดำ",
                "English name": "Blackchin tilapia",
                "Scientific name": "Sarotherodon melanotheron",
            },
        ]))

        a, b = st.columns(2)
        with a:
            st.image(
                str(sets["Set 1 — 10 Nile tilapia"][0]),
                caption="Nile tilapia — label supplied by filename",
                use_column_width=True,
            )
        with b:
            black_example = next(
                p for p in sets["Set 3 — 6 Nile + 4 blackchin tilapia"]
                if p.name.lower().startswith("black")
            )
            st.image(
                str(black_example),
                caption="Blackchin tilapia — label supplied by filename",
                use_column_width=True,
            )

        st.info(
            "These are different species. A real identification guide should "
            "compare expert-verified head, chin, fin, and tail features. "
            "Do not rely on chin colour alone. The supplied images and "
            "identification guidance need expert review before public use."
        )
        st.caption(
            "Species screening does not test pathogens or certify food safety."
        )

elif page == "Sampling risk":
    st.header("What can a random sample miss?")
    st.write(
        "A clean sample is useful evidence, but it cannot prove that "
        "the rest of the lot contains no blackchin tilapia."
    )

    total = st.number_input(
        "Fish in lot", min_value=10, max_value=1000, value=100
    )
    mixed = st.number_input(
        "Blackchin fish actually present — hypothetical",
        min_value=0,
        max_value=int(total),
        value=1,
    )
    sample = st.slider(
        "Number randomly sampled",
        min_value=1,
        max_value=int(total),
        value=min(10, int(total)),
    )

    n, k, s = int(total), int(mixed), int(sample)
    miss_probability = (
        comb(n - k, s) / comb(n, s)
        if s <= n - k else 0.0
    )
    inclusion_probability = 1 - miss_probability

    a, b = st.columns(2)
    a.metric(
        "Chance sample includes ≥1 blackchin fish",
        f"{inclusion_probability:.1%}",
    )
    b.metric(
        "Chance sample misses all blackchin fish",
        f"{miss_probability:.1%}",
    )

    st.caption(
        "Assumes a genuinely random sample without replacement and a known "
        "hypothetical number of blackchin fish. This calculates inclusion "
        "in the sample—not successful AI detection. AI mistakes can make "
        "actual detection worse."
    )

    st.subheader("Practical risk reduction")
    st.markdown(
        """
- Sample from across containers and throughout unloading, not just the top.
- Increase sample size when there are concerns about the source.
- Keep different lots separate during transport, storage, and sale.
- Inspect fish during normal sorting; refer uncertain fish for review.
- Hold the lot when a suspected mismatch is found.
- Describe results as sample findings, never a whole-lot guarantee.
"""
    )

st.divider()
st.caption(
    "Prototype data lasts only for the current Streamlit session. "
    "A production system needs validated AI, persistent storage, "
    "role-based access, review records, and public lot URLs for QR labels."
)
