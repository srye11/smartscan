import streamlit as st
from detector import detect_allergens
from database import init_db, create_user, verify_login, save_profile, load_profile, save_scan, load_scans, delete_scan

init_db()

st.set_page_config(page_title="SmartScan", page_icon="🍽️", layout="wide")

BIG9 = ["Milk", "Egg", "Peanut", "Tree Nut", "Soy", "Wheat", "Fish", "Shellfish", "Sesame"]

# ---- Custom styling ----
st.markdown("""
<style>
    section[data-testid="stSidebar"] {
        background-color: #0d3b3e;
    }
    section[data-testid="stSidebar"] * {
        color: white !important;
    }
    div.stButton > button {
        background-color: #0f7a82;
        color: white;
        border-radius: 8px;
        border: none;
    }
    div.stButton > button:hover {
        background-color: #0a5a60;
        color: white;
    }
    .severity-severe {
        background-color: #fdeaea;
        border-left: 5px solid #d64545;
        padding: 10px 14px;
        border-radius: 8px;
        margin-bottom: 8px;
    }
    .severity-moderate {
        background-color: #fff6e5;
        border-left: 5px solid #e0a324;
        padding: 10px 14px;
        border-radius: 8px;
        margin-bottom: 8px;
    }
    .severity-mild {
        background-color: #eef7ee;
        border-left: 5px solid #4a9d4a;
        padding: 10px 14px;
        border-radius: 8px;
        margin-bottom: 8px;
    }
    .recipe-card {
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 14px;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# ---- Session state ----
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "email" not in st.session_state:
    st.session_state.email = None
if "full_name" not in st.session_state:
    st.session_state.full_name = None
if "allergy_profile" not in st.session_state:
    st.session_state.allergy_profile = []
if "scan_history" not in st.session_state:
    st.session_state.scan_history = []

# ---- Sample recipes ----
RECIPES = [
    {
        "name": "Avocado Toast on Gluten-Light Bread", "tags": ["Wheat"], "time": "10 min", "kcal": 320, "difficulty": "Easy",
        "ingredients": ["2 slices gluten-light bread", "1 ripe avocado", "Salt & pepper", "Chili flakes (optional)", "Squeeze of lemon"],
        "steps": ["Toast the bread slices.", "Mash the avocado with lemon, salt, and pepper.", "Spread over toast.", "Top with chili flakes if desired."]
    },
    {
        "name": "Oat Milk Banana Pancakes", "tags": ["Wheat"], "time": "20 min", "kcal": 410, "difficulty": "Easy",
        "ingredients": ["1 cup flour", "1 ripe banana, mashed", "1 cup oat milk", "1 tsp baking powder", "Pinch of salt"],
        "steps": ["Mix flour, baking powder, and salt.", "Whisk in mashed banana and oat milk until smooth.", "Cook spoonfuls of batter on a lightly oiled pan, 2 min per side.", "Serve warm."]
    },
    {
        "name": "Chickpea Stir-Fry with Rice", "tags": [], "time": "25 min", "kcal": 520, "difficulty": "Medium",
        "ingredients": ["1 can chickpeas, drained", "2 cups cooked rice", "1 bell pepper, sliced", "2 tbsp soy-free seasoning sauce", "1 tbsp oil", "Garlic, chopped"],
        "steps": ["Heat oil, sauté garlic until fragrant.", "Add bell pepper and chickpeas, stir-fry 5 min.", "Add seasoning sauce, cook 2 more minutes.", "Serve over rice."]
    },
    {
        "name": "Grilled Salmon with Quinoa", "tags": ["Fish"], "time": "30 min", "kcal": 480, "difficulty": "Medium",
        "ingredients": ["1 salmon fillet", "1 cup cooked quinoa", "Olive oil", "Lemon", "Salt & pepper", "Steamed vegetables"],
        "steps": ["Season salmon with salt, pepper, and olive oil.", "Grill or pan-sear 4-5 min per side.", "Serve over quinoa with steamed vegetables and a lemon wedge."]
    },
    {
        "name": "Berry Smoothie Bowl", "tags": ["Milk"], "time": "8 min", "kcal": 290, "difficulty": "Easy",
        "ingredients": ["1 cup mixed berries (frozen)", "1/2 cup yogurt", "1 banana", "Granola for topping"],
        "steps": ["Blend berries, yogurt, and banana until thick.", "Pour into a bowl.", "Top with granola and extra berries."]
    },
    {
        "name": "Lentil Soup with Flatbread", "tags": ["Wheat"], "time": "35 min", "kcal": 380, "difficulty": "Easy",
        "ingredients": ["1 cup lentils", "1 onion, diced", "2 carrots, diced", "4 cups vegetable broth", "Cumin, salt, pepper", "Flatbread to serve"],
        "steps": ["Sauté onion and carrots until soft.", "Add lentils, broth, and spices.", "Simmer 25 minutes until lentils are tender.", "Serve hot with warm flatbread."]
    },
    {
        "name": "Peanut-Free Veggie Stir Fry", "tags": ["Soy"], "time": "20 min", "kcal": 350, "difficulty": "Easy",
        "ingredients": ["Mixed vegetables (broccoli, carrot, snap peas)", "2 tbsp soy sauce", "1 tbsp sesame-free oil", "Garlic and ginger, minced"],
        "steps": ["Heat oil, sauté garlic and ginger.", "Add vegetables, stir-fry 5-7 minutes until crisp-tender.", "Add soy sauce, toss to coat, and serve."]
    },
    {
        "name": "Shrimp-Free Garlic Rice Bowl", "tags": [], "time": "15 min", "kcal": 400, "difficulty": "Easy",
        "ingredients": ["2 cups cooked rice", "3 cloves garlic, minced", "2 eggs (optional)", "Green onions, chopped", "Soy-free seasoning"],
        "steps": ["Fry garlic in oil until golden.", "Add rice, stir well to combine.", "Push rice aside, scramble eggs in the same pan if using.", "Mix together, top with green onions."]
    },
        {
        "name": "Nasi Lemak", "tags": ["Fish", "Shellfish"], "time": "40 min", "kcal": 550, "difficulty": "Medium",
        "ingredients": ["2 cups rice", "1 cup coconut milk", "2 pandan leaves", "1/2 cup ikan bilis (anchovies)", "2 tbsp belacan (shrimp paste)", "3 shallots", "2 red chilies", "Hard-boiled eggs (optional)", "Cucumber slices"],
        "steps": ["Cook rice with coconut milk and pandan leaves until fluffy.", "Blend shallots, chilies, and belacan for the sambal base.", "Fry the sambal paste with ikan bilis until fragrant and slightly caramelized.", "Serve rice with sambal, cucumber, and boiled egg on the side."]
    },
    {
        "name": "Roti Canai", "tags": ["Wheat"], "time": "45 min", "kcal": 300, "difficulty": "Medium",
        "ingredients": ["2 cups flour", "1 egg", "3/4 cup water", "2 tbsp condensed milk", "Ghee or oil for layering", "Pinch of salt"],
        "steps": ["Mix flour, egg, water, condensed milk, and salt into a soft dough.", "Knead well, coat with oil, and rest for at least 2 hours.", "Flatten and stretch each portion thin, fold into layers, and rest again.", "Pan-fry on a hot griddle with a little oil until golden and flaky on both sides."]
    },
    {
        "name": "Char Kway Teow", "tags": ["Shellfish", "Egg", "Soy"], "time": "20 min", "kcal": 600, "difficulty": "Medium",
        "ingredients": ["300g flat rice noodles (kway teow)", "6 prawns, peeled", "2 eggs", "1 cup bean sprouts", "2 tbsp dark soy sauce", "1 tbsp light soy sauce", "2 cloves garlic, chopped", "Chinese chives, chopped"],
        "steps": ["Heat oil in a hot wok, sauté garlic until fragrant.", "Add prawns, stir-fry until pink.", "Push aside, crack in eggs and scramble lightly.", "Add noodles, soy sauces, and bean sprouts. Toss everything together on high heat.", "Add chives, stir briefly, and serve immediately."]
    },
    {
        "name": "Mee Goreng Mamak", "tags": ["Wheat", "Egg", "Soy"], "time": "20 min", "kcal": 480, "difficulty": "Easy",
        "ingredients": ["300g yellow egg noodles", "1 egg", "2 tbsp soy sauce", "1 tbsp chili paste", "1/2 cup potato, diced and fried", "1 cup bean sprouts", "Lime wedge to serve"],
        "steps": ["Heat oil, fry chili paste until fragrant.", "Add noodles and soy sauce, toss well.", "Push noodles aside, crack in egg and scramble.", "Mix in fried potato and bean sprouts, stir-fry 2-3 minutes.", "Serve with a lime wedge."]
    },
    {
        "name": "Satay with Peanut Sauce", "tags": ["Peanut"], "time": "40 min", "kcal": 420, "difficulty": "Medium",
        "ingredients": ["500g chicken, cubed", "Turmeric, coriander, lemongrass (marinade)", "1 cup ground peanuts", "1 tbsp chili paste", "1 tbsp tamarind juice", "Coconut milk", "Skewers"],
        "steps": ["Marinate chicken with turmeric, coriander, and lemongrass for at least 1 hour.", "Thread onto skewers and grill until charred and cooked through.", "For the sauce, simmer ground peanuts, chili paste, tamarind juice, and coconut milk until thickened.", "Serve skewers with peanut sauce, sliced cucumber, and ketupat."]
    },
    {
        "name": "Beef Rendang", "tags": [], "time": "90 min", "kcal": 490, "difficulty": "Medium",
        "ingredients": ["500g beef, cubed", "2 cups coconut milk", "3 tbsp rendang spice paste (lemongrass, galangal, chili, shallots)", "2 tbsp kerisik (toasted coconut paste)", "Kaffir lime leaves", "Tamarind juice"],
        "steps": ["Sauté the spice paste until fragrant and oil separates.", "Add beef, stir to coat evenly in the paste.", "Pour in coconut milk, add lime leaves and tamarind juice, bring to a simmer.", "Cook on low heat for 60-75 minutes, stirring occasionally, until sauce thickens and darkens.", "Stir in kerisik near the end for richness. Serve with rice."]
    },
        {
        "name": "Vegetable Fried Rice", "tags": ["Egg", "Soy"], "time": "15 min", "kcal": 380, "difficulty": "Easy",
        "ingredients": ["2 cups cooked rice (day-old)", "1 egg", "1/2 cup mixed vegetables (carrot, peas, corn)", "2 tbsp soy sauce", "2 cloves garlic, minced", "Spring onion, chopped"],
        "steps": ["Heat oil, sauté garlic until fragrant.", "Push aside, crack in egg and scramble.", "Add rice and vegetables, stir-fry 3-4 minutes.", "Add soy sauce, toss well, top with spring onion."]
    },
    {
        "name": "Chicken Rice Porridge (Congee)", "tags": [], "time": "40 min", "kcal": 280, "difficulty": "Easy",
        "ingredients": ["1/2 cup rice", "200g chicken breast, shredded", "6 cups water or broth", "Ginger, sliced", "Spring onion, chopped", "Salt to taste"],
        "steps": ["Bring rice, water, and ginger to a boil.", "Simmer on low heat, stirring occasionally, for 30 minutes until thick and creamy.", "Add shredded chicken, cook another 5 minutes.", "Season with salt, top with spring onion."]
    },
    {
        "name": "Egg Fried Noodles", "tags": ["Wheat", "Egg", "Soy"], "time": "15 min", "kcal": 420, "difficulty": "Easy",
        "ingredients": ["250g yellow noodles", "2 eggs", "1 cup bean sprouts", "2 tbsp soy sauce", "2 cloves garlic, chopped", "Spring onion"],
        "steps": ["Boil noodles briefly, drain.", "Heat oil, sauté garlic, scramble in eggs.", "Add noodles and soy sauce, toss well.", "Add bean sprouts, stir-fry 2 minutes, top with spring onion."]
    },
    {
        "name": "Garlic Butter Pasta", "tags": ["Wheat", "Milk"], "time": "20 min", "kcal": 450, "difficulty": "Easy",
        "ingredients": ["200g pasta", "3 tbsp butter", "4 cloves garlic, minced", "Parmesan cheese, grated", "Parsley, chopped", "Salt & pepper"],
        "steps": ["Cook pasta according to package instructions, reserve 1/2 cup pasta water.", "Melt butter, sauté garlic until golden.", "Toss in pasta with a splash of pasta water.", "Top with parmesan, parsley, salt, and pepper."]
    },
    {
        "name": "Sweet and Sour Chicken", "tags": ["Soy"], "time": "30 min", "kcal": 460, "difficulty": "Medium",
        "ingredients": ["300g chicken breast, cubed", "1 bell pepper, diced", "1/2 pineapple, chunked", "3 tbsp ketchup", "2 tbsp soy sauce", "2 tbsp vinegar", "1 tbsp sugar", "Cornstarch for coating"],
        "steps": ["Coat chicken in cornstarch, pan-fry until golden and cooked through.", "Mix ketchup, soy sauce, vinegar, and sugar for the sauce.", "Stir-fry bell pepper and pineapple briefly.", "Add chicken and sauce, toss until coated and glossy."]
    },
    {
        "name": "Vegetable Curry with Rice", "tags": [], "time": "30 min", "kcal": 400, "difficulty": "Easy",
        "ingredients": ["2 cups mixed vegetables (potato, carrot, cauliflower)", "1 cup coconut milk", "2 tbsp curry powder", "1 onion, sliced", "2 cloves garlic", "2 cups cooked rice"],
        "steps": ["Sauté onion and garlic until soft.", "Add curry powder, stir until fragrant.", "Add vegetables and coconut milk, simmer 15-20 minutes until tender.", "Serve hot over rice."]
    },
    {
        "name": "Grilled Chicken Salad", "tags": [], "time": "20 min", "kcal": 350, "difficulty": "Easy",
        "ingredients": ["1 chicken breast", "Mixed salad greens", "Cherry tomatoes", "Cucumber", "Olive oil", "Lemon juice", "Salt & pepper"],
        "steps": ["Season chicken with salt and pepper, grill until cooked through.", "Slice chicken.", "Toss salad greens, tomatoes, and cucumber with olive oil and lemon juice.", "Top salad with sliced chicken."]
    },
    {
        "name": "Tuna Sandwich", "tags": ["Fish", "Wheat", "Egg"], "time": "10 min", "kcal": 340, "difficulty": "Easy",
        "ingredients": ["1 can tuna, drained", "2 tbsp mayonnaise", "4 slices bread", "Lettuce", "Salt & pepper"],
        "steps": ["Mix tuna with mayonnaise, salt, and pepper.", "Toast bread if desired.", "Layer lettuce and tuna mixture between bread slices."]
    },
    {
        "name": "Banana Oat Muffins", "tags": ["Wheat", "Egg", "Milk"], "time": "35 min", "kcal": 290, "difficulty": "Medium",
        "ingredients": ["2 ripe bananas, mashed", "1 cup oats", "1 cup flour", "1 egg", "1/2 cup milk", "1 tsp baking powder", "2 tbsp honey"],
        "steps": ["Preheat oven to 180°C.", "Mix mashed banana, egg, milk, and honey.", "Fold in oats, flour, and baking powder until just combined.", "Pour into muffin tin, bake 20-25 minutes until golden."]
    },
    {
        "name": "Steamed Fish with Ginger and Soy Sauce", "tags": ["Fish", "Soy"], "time": "20 min", "kcal": 250, "difficulty": "Easy",
        "ingredients": ["1 whole white fish (or fillet)", "Ginger, julienned", "2 tbsp soy sauce", "1 tbsp sesame oil", "Spring onion, sliced"],
        "steps": ["Place fish on a steaming plate, top with ginger.", "Steam 10-15 minutes until cooked through.", "Heat soy sauce and sesame oil, pour over fish.", "Top with spring onion before serving."]
    },
    {
        "name": "Stir-Fried Tofu and Vegetables", "tags": ["Soy"], "time": "15 min", "kcal": 320, "difficulty": "Easy",
        "ingredients": ["1 block firm tofu, cubed", "Mixed vegetables (broccoli, carrot, mushroom)", "2 tbsp soy sauce", "2 cloves garlic, minced", "1 tbsp oil"],
        "steps": ["Pan-fry tofu cubes until golden on all sides, set aside.", "Sauté garlic, add vegetables, stir-fry 3-4 minutes.", "Return tofu to pan, add soy sauce, toss to combine."]
    },
]

# ---- Screen: Auth ----
def auth_screen():
    st.markdown("## 🍽️ SmartScan")
    st.caption("Allergen-safe food, personalised for you.")

    tab1, tab2 = st.tabs(["Sign Up", "Log In"])

    with tab1:
        st.subheader("Create your account")
        full_name = st.text_input("Full Name", key="signup_name")
        email = st.text_input("Email address", key="signup_email")
        password = st.text_input("Password", type="password", key="signup_pw")
        selected = st.multiselect("Declare your allergies (Big 9)", BIG9, key="signup_allergies")

        if st.button("Get started — it's free"):
            if not full_name or not email or not password:
                st.warning("Please fill in all fields.")
            else:
                success = create_user(email.strip().lower(), full_name.strip(), password)
                if success:
                    save_profile(email.strip().lower(), selected)
                    st.success("Account created! Please log in.")
                else:
                    st.error("An account with this email already exists.")

    with tab2:
        st.subheader("Log in")
        login_email = st.text_input("Email address", key="login_email")
        login_password = st.text_input("Password", type="password", key="login_pw")

        if st.button("Log In"):
            full_name = verify_login(login_email.strip().lower(), login_password)
            if full_name:
                st.session_state.logged_in = True
                st.session_state.email = login_email.strip().lower()
                st.session_state.full_name = full_name
                st.session_state.allergy_profile = load_profile(st.session_state.email)
                st.session_state.scan_history = load_scans(st.session_state.email)
                st.rerun()
            else:
                st.error("Incorrect email or password.")

# ---- Severity display ----
def severity_box(allergen, severity, explanation):
    css_class = {"Severe": "severity-severe", "Moderate": "severity-moderate", "Mild": "severity-mild"}.get(severity, "severity-mild")
    st.markdown(f"""
    <div class="{css_class}">
        <strong>{allergen.title()}</strong> — {severity}<br>
        <span style="font-size: 0.9em;">{explanation}</span>
    </div>
    """, unsafe_allow_html=True)

def display_result(result):
    if result.get("safe"):
        st.success("✅ No declared allergens detected.")
    else:
        st.error("⚠️ Allergens detected!")
        for a in result.get("flagged_allergens", []):
            severity_box(a["allergen"], a["severity"], a["explanation"])

# ---- Screen: Scan ----
def scan_screen():
    st.markdown("### Scan an ingredient label")
    st.caption(f"Checking against: {', '.join(st.session_state.allergy_profile) if st.session_state.allergy_profile else 'no allergies set'}")

    input_method = st.radio("How do you want to scan?", ["📷 Use camera", "📁 Upload a photo"], horizontal=True)

    if input_method == "📷 Use camera":
        uploaded_file = st.camera_input("Take a photo of the label")
    else:
        uploaded_file = st.file_uploader("Upload a photo of the label", type=["jpg", "jpeg", "png"])

    if uploaded_file is not None:
        st.image(uploaded_file, caption="Captured label", width=300)

        if st.button("Analyze"):
            with st.spinner("Analyzing label..."):
                temp_path = "temp_upload.jpg"
                with open(temp_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())

                result = detect_allergens(temp_path, st.session_state.allergy_profile)

            if result is None:
                st.error("Something went wrong reading the label. Try again.")
            else:
                display_result(result)
                image_bytes = uploaded_file.getvalue()
                save_scan(st.session_state.email, image_bytes, result)
                st.session_state.scan_history = load_scans(st.session_state.email)

# ---- Screen: History ----
def history_screen():
    st.markdown("### Scan history")

    if not st.session_state.scan_history:
        st.info("No scans yet.")
    else:
        total = len(st.session_state.scan_history)
        for i, entry in enumerate(st.session_state.scan_history):
            scan_num = total - i
            with st.expander(f"Scan {scan_num}" + (" (most recent)" if i == 0 else "")):
                st.image(entry["image"], width=250)
                display_result(entry["result"])
                if st.button("🗑️ Delete this scan", key=f"delete_{entry['db_id']}"):
                    delete_scan(st.session_state.email, entry["db_id"])
                    st.session_state.scan_history = load_scans(st.session_state.email)
                    st.rerun()

# ---- Screen: Allergy Profile ----
def profile_screen():
    st.markdown("### Your allergy profile")
    selected = st.multiselect("Select your allergies (Big 9)", BIG9, default=st.session_state.allergy_profile)

    if st.button("Save profile"):
        st.session_state.allergy_profile = selected
        save_profile(st.session_state.email, selected)
        st.success("Profile updated.")

# ---- Screen: Safe Recipes ----
def recipes_screen():
    st.markdown("### Safe Recipes For You")
    st.caption("All recipes below avoid your declared allergens")

    user_allergies = set(st.session_state.allergy_profile)
    safe_recipes = [r for r in RECIPES if not (set(r["tags"]) & user_allergies)]

    if not safe_recipes:
        st.info("No matching recipes found — try adjusting your allergy profile.")

    for recipe in safe_recipes:
        with st.expander(f"✓ {recipe['name']} — {recipe['time']} · {recipe['kcal']} kcal · {recipe['difficulty']}"):
            st.markdown("**Ingredients:**")
            for ing in recipe["ingredients"]:
                st.markdown(f"- {ing}")
            st.markdown("**Steps:**")
            for i, step in enumerate(recipe["steps"], start=1):
                st.markdown(f"{i}. {step}")

# ---- Main app router ----
if not st.session_state.logged_in:
    auth_screen()
else:
    with st.sidebar:
        st.markdown("## 🍽️ SmartScan")
        st.caption(f"Logged in as {st.session_state.full_name}")
        page = st.radio("Navigate", ["Scan label", "Scan history", "Allergy profile", "Safe recipes"], label_visibility="collapsed")
        if st.button("Log out"):
            st.session_state.logged_in = False
            st.session_state.email = None
            st.rerun()

    if page == "Scan label":
        scan_screen()
    elif page == "Scan history":
        history_screen()
    elif page == "Allergy profile":
        profile_screen()
    elif page == "Safe recipes":
        recipes_screen()