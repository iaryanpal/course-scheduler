# app.py
import streamlit as st
import pandas as pd
from pysat.formula import CNF
from pysat.solvers import Solver
from io import BytesIO

# -------------------- APP CONFIG --------------------
st.set_page_config(
    page_title="Course Scheduler",
    page_icon="📅",
    layout="centered",
    initial_sidebar_state="expanded"
)

# -------------------- USER DATABASE --------------------
# For demo: hardcoded users (replace with DB in production)
USERS = {
    "faculty1": {"password": "pass123", "role": "Faculty"},
    "faculty2": {"password": "pass456", "role": "Faculty"},
    "admin": {"password": "admin123", "role": "Admin"}
}

# -------------------- SESSION STATE --------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.role = None
    st.session_state.username = None

# -------------------- LOGIN FUNCTION --------------------
def login(username, password):
    if username in USERS and USERS[username]["password"] == password:
        st.session_state.logged_in = True
        st.session_state.role = USERS[username]["role"]
        st.session_state.username = username
        return True
    return False

def logout():
    st.session_state.logged_in = False
    st.session_state.role = None
    st.session_state.username = None

# -------------------- SAT Solver Logic --------------------
def generate_timetable(data):
    courses = data["Course"].tolist()
    faculty_map = dict(zip(data["Course"], data["Faculty"]))
    preferences = {}
    all_slots = set()

    for _, row in data.iterrows():
        pref_list = [s.strip() for s in row["PreferredSlots"].split(",")]
        preferences[row["Faculty"]] = pref_list
        all_slots.update(pref_list)
    slots = sorted(list(all_slots))

    # Map (course, slot) -> SAT variable
    var_map = {}
    counter = 1
    for c in courses:
        for s in slots:
            var_map[(c, s)] = counter
            counter += 1

    cnf = CNF()

    # Each course in at least one preferred slot
    for c in courses:
        preferred_vars = [var_map[(c, s)] for s in preferences[faculty_map[c]]]
        cnf.append(preferred_vars)

    # At most one slot per course
    for c in courses:
        for i in range(len(slots)):
            for j in range(i+1, len(slots)):
                cnf.append([-var_map[(c, slots[i])], -var_map[(c, slots[j])]])

    # No professor clash
    for s in slots:
        prof_courses = {}
        for c in courses:
            p = faculty_map[c]
            prof_courses.setdefault(p, []).append(c)
        for p, pcourses in prof_courses.items():
            for i in range(len(pcourses)):
                for j in range(i+1, len(pcourses)):
                    cnf.append([-var_map[(pcourses[i], s)], -var_map[(pcourses[j], s)]])

    with Solver(bootstrap_with=cnf) as solver:
        if solver.solve():
            model = solver.get_model()
            timetable = []
            for (c, s), var in var_map.items():
                if var in model:
                    timetable.append({"Course": c, "Faculty": faculty_map[c], "Slot": s})
            return pd.DataFrame(timetable)
        else:
            return None

# -------------------- LOGIN PAGE --------------------
if not st.session_state.logged_in:
    st.title("🔐 Course Scheduler Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if login(username, password):
            st.success(f"✅ Welcome {st.session_state.username} ({st.session_state.role})")
            st.rerun()
        else:
            st.error("❌ Invalid username or password")

else:
    # -------------------- DASHBOARD --------------------
    st.sidebar.title("Navigation")
    st.sidebar.write(f"👤 Logged in as: {st.session_state.username} ({st.session_state.role})")
    if st.sidebar.button("🚪 Logout"):
        logout()
        st.rerun()

    if st.session_state.role == "Faculty":
        st.title("📅 Faculty Timetable Submission")
        st.markdown("Upload your **course preferences** in CSV format and view the generated timetable.")

        uploaded_file = st.file_uploader("Upload Faculty Preferences (CSV)", type=["csv"])
        if uploaded_file:
            data = pd.read_csv(uploaded_file)
            st.write("Uploaded Preferences Preview:", data)

            if st.button("Generate Timetable", type="primary"):
                timetable_df = generate_timetable(data)
                if timetable_df is not None:
                    st.success("✅ Timetable generated successfully!")
                    st.dataframe(timetable_df)

                    # Export options
                    csv_export = timetable_df.to_csv(index=False).encode('utf-8')
                    excel_buffer = BytesIO()
                    timetable_df.to_excel(excel_buffer, index=False)
                    excel_data = excel_buffer.getvalue()

                    st.download_button("⬇ Download CSV", csv_export, "timetable.csv", "text/csv")
                    st.download_button("⬇ Download Excel", excel_data, "timetable.xlsx", "application/vnd.ms-excel")
                else:
                    st.error("❌ No valid timetable found for given constraints")

    elif st.session_state.role == "Admin":
        st.title("🛠 Admin Timetable Management")
        st.markdown("Department head can **review and approve** generated timetables here.")

        uploaded_timetable = st.file_uploader("Upload Generated Timetable", type=["csv", "xlsx"])
        if uploaded_timetable:
            if uploaded_timetable.name.endswith(".csv"):
                timetable_df = pd.read_csv(uploaded_timetable)
            else:
                timetable_df = pd.read_excel(uploaded_timetable)

            st.write("📋 Timetable Preview:", timetable_df)

            # Approval system
            if st.button("✅ Approve Timetable", type="primary"):
                st.success("Timetable Approved and Finalized!")

            if st.button("🔄 Request Changes"):
                st.warning("Request sent to faculty for updates.")
