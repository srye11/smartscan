import streamlit as st
from detector import detect_allergens
from database import init_db, save_profile, load_profile, save_scan, load_scans

init_db()

st.set_page_config(page_title="SmartScan", page_icon="🍽️")

# ---- Session state setup (holds data across screen switches) ----
if "screen" not in st.session_state:
    st.session_state.screen = "onboarding"
if "allergy_profile" not in st.session_state:
    st.session_state.allergy_profile = load_profile()
if "scan_history" not in st.session_state:
    st.session_state.scan_history = load_scans()

BIG9 = ["Milk", "Egg", "Peanut", "Tree Nut", "Soy", "Wheat", "Fish", "Shellfish", "Sesame"]

# ---- Screen 1: Onboarding ----
def onboarding_screen():
    st.title("🍽️ SmartScan")
    st.subheader("Set up your allergy profile")

    selected = st.multiselect(
        "Select your allergies (Big 9)",
        BIG9,
        default=st.session_state.allergy_profile
    )

    if st.button("Save and continue"):
        st.session_state.allergy_profile = selected
        save_profile(selected)
        st.session_state.screen = "scan"
        st.rerun()

# ---- Screen 2: Scan + Result ----
def scan_screen():
    st.title("🍽️ SmartScan")
    st.subheader("Scan an ingredient label")

    if st.session_state.allergy_profile:
        st.caption(f"Checking against: {', '.join(st.session_state.allergy_profile)}")
    else:
        st.warning("No allergies set. Go to your profile to add some.")

    uploaded_file = st.file_uploader("Upload a photo of the label", type=["jpg", "jpeg", "png"])

    if uploaded_file is not None:
        st.image(uploaded_file, caption="Uploaded label", width=300)

        if st.button("Analyze"):
            with st.spinner("Analyzing label..."):
                # save uploaded file temporarily so detect_allergens can read it
                temp_path = "temp_upload.jpg"
                with open(temp_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())

                result = detect_allergens(temp_path, st.session_state.allergy_profile)

            if result is None:
                st.error("Something went wrong reading the label. Try again.")
            else:
                display_result(result)
                image_bytes = uploaded_file.getvalue()
                st.session_state.scan_history.append({
                    "result": result,
                    "image": image_bytes
                })
                save_scan(image_bytes, result)

    if st.button("View scan history"):
        st.session_state.screen = "history"
        st.rerun()

    if st.button("Edit allergy profile"):
        st.session_state.screen = "onboarding"
        st.rerun()

def display_result(result):
    if result.get("safe"):
        st.success("✅ No declared allergens detected.")
    else:
        st.error("⚠️ Allergens detected!")
        for a in result.get("flagged_allergens", []):
            severity = a["severity"]
            color = {"Severe": "🔴", "Moderate": "🟠", "Mild": "🟡"}.get(severity, "⚪")
            st.markdown(f"{color} **{a['allergen'].title()}** — {severity}")
            st.caption(a["explanation"])

# ---- Screen 3: Scan History ----
def history_screen():
    st.title("🍽️ SmartScan")
    st.subheader("Scan history")

    if not st.session_state.scan_history:
        st.info("No scans yet.")
    else:
        for i, entry in enumerate(reversed(st.session_state.scan_history), start=1):
            scan_num = len(st.session_state.scan_history) - i + 1
            with st.expander(f"Scan {scan_num}"):
                st.image(entry["image"], width=250)
                display_result(entry["result"])

    if st.button("Back to scan"):
        st.session_state.screen = "scan"
        st.rerun()

# ---- Router ----
if st.session_state.screen == "onboarding":
    onboarding_screen()
elif st.session_state.screen == "scan":
    scan_screen()
elif st.session_state.screen == "history":
    history_screen()