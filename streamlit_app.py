import streamlit as st
from sqlalchemy.orm import Session
from datetime import datetime
import json

from app.database import SessionLocal, User, UserProfile, Conversation
from app.agent import FitnessCoachAgent

# TODO: Add user profile pictures/avatars
# TODO: Maybe add a progress tracking dashboard?

st.set_page_config(
    page_title="Fitness Coach AI",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Some basic styling - went with a teal theme because it seemed easier on the eyes 
st.markdown("""
<style>
    .stApp {
        background: linear-gradient(135deg, #e0f2f1 0%, #b2dfdb 100%);
    }
</style>
""", unsafe_allow_html=True)

if 'user' not in st.session_state:
    st.session_state.user = None
if 'messages' not in st.session_state:
    st.session_state.messages = []

def get_db():
    return SessionLocal()

def register_user(username: str, password: str, db: Session):
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        return False, "Username already exists"

    # Not hashing passwords because this is just a demo and not going to production
    # If I deploy this for real I'll add bcrypt or something
    new_user = User(username=username, password=password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Create empty profile for the user
    profile = UserProfile(user_id=new_user.id)
    db.add(profile)
    db.commit()

    return True, "Account created successfully!"

def login_user(username: str, password: str, db: Session):
    user = db.query(User).filter(User.username == username).first()

    if not user or user.password != password:
        return None, "Invalid credentials"

    return user, "Login successful"

def load_conversation_history(user_id: int, db: Session):
    conversations = db.query(Conversation).filter(
        Conversation.user_id == user_id
    ).order_by(Conversation.timestamp).all()
    
    messages = []
    for conv in conversations:
        messages.append({
            "role": conv.role,
            "content": conv.content,
            "timestamp": conv.timestamp
        })
    return messages

def save_message(user_id: int, role: str, content: str, db: Session):
    msg = Conversation(
        user_id=user_id,
        role=role,
        content=content
    )
    db.add(msg)
    db.commit()

def get_user_data(user_id: int, db: Session) -> dict:
    user = db.query(User).filter(User.id == user_id).first()
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()

    # Pack up all the user info for the agent
    # Using defaults for missing profile data so the agent doesn't crash
    data = {
        "username": user.username,
        "age": profile.age if profile else None,
        "weight": profile.weight if profile else None,
        "height": profile.height if profile else None,
        "fitness_goal": profile.fitness_goal if profile else "general fitness",
        "activity_level": profile.activity_level if profile else "moderate",
        "dietary_restrictions": profile.dietary_restrictions if profile else "none",
        "preferences": profile.preferences if profile else "none",
    }

    return data

def update_profile(user_id: int, profile_data: dict, db: Session):
    profile = db.query(UserProfile).filter(
        UserProfile.user_id == user_id
    ).first()

    if not profile:
        return

    for field in (
        "age",
        "weight",
        "height",
        "fitness_goal",
        "activity_level",
        "dietary_restrictions",
        "preferences",
    ):
        if field in profile_data and profile_data[field] is not None:
            setattr(profile, field, profile_data[field])

    db.commit()

def auth_view():
    # Center the login form using columns trick
    _, col2, _ = st.columns([1, 2, 1])

    with col2:
        st.title("🏋️ Fitness Coach AI")
        st.write("Your AI-powered personal trainer")

        tab1, tab2 = st.tabs(["Login", "Register"])

        with tab1:
            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                login_button = st.form_submit_button("Login", use_container_width=True)

                if login_button:
                    if not username or not password:
                        st.error("Please enter username and password")
                    else:
                        db = get_db()
                        user, message = login_user(username, password, db)
                        db.close()

                        if user:
                            st.session_state.user = {'id': user.id, 'username': user.username}
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)

        with tab2:
            with st.form("register_form"):
                new_username = st.text_input("Choose Username")
                new_password = st.text_input("Choose Password", type="password")
                confirm_password = st.text_input("Confirm Password", type="password")
                register_button = st.form_submit_button("Register")

                if register_button:
                    if not new_username or not new_password or not confirm_password:
                        st.error("Please fill all fields")
                    elif new_password != confirm_password:
                        st.error("Passwords don't match!")
                    else:
                        db = get_db()
                        success, message = register_user(new_username, new_password, db)
                        db.close()

                        if success:
                            st.success(message + " Please login.")
                        else:
                            st.error(message)

def chat_page():
    db = get_db()

    # Show username in sidebar
    st.sidebar.write(f"### Logged in as: {st.session_state.user['username']}")
    st.sidebar.write("---")

    profile = db.query(UserProfile).filter(UserProfile.user_id == st.session_state.user['id']).first()

    with st.sidebar.expander("Update Profile"):
        with st.form("profile_form"):
            age_value = 0
            if profile.age:
                age_value = profile.age
            age = st.number_input("Age", value=age_value, min_value=0, max_value=120)

            weight_value = 0.0
            if profile.weight:
                weight_value = float(profile.weight)
            weight = st.number_input("Weight (lb)", value=weight_value, min_value=0.0, max_value=1000.0, step=0.1)

            # Storing as decimal in DB (5.75 = 5'9") but showing as feet/inches for UX
            height_value = 0.0
            if profile.height:
                height_value = float(profile.height)

            col1, col2 = st.columns(2)
            with col1:
                feet = int(height_value)
                height_ft = st.number_input("Feet", value=feet, min_value=0, max_value=8)
            with col2:
                inches = int((height_value - int(height_value)) * 12)
                height_in = st.number_input("Inches", value=inches, min_value=0, max_value=11)

            height = height_ft + (height_in / 12.0)

            goal_options = ["", "lose_weight", "gain_muscle", "maintain", "improve_endurance"]
            goal_index = 0
            if profile.fitness_goal and profile.fitness_goal in goal_options:
                goal_index = goal_options.index(profile.fitness_goal)
            fitness_goal = st.selectbox("Fitness Goal", options=goal_options, index=goal_index)

            activity_options = ["", "sedentary", "light", "moderate", "active", "very_active"]
            activity_index = 0
            if profile.activity_level and profile.activity_level in activity_options:
                activity_index = activity_options.index(profile.activity_level)
            activity_level = st.selectbox("Activity Level", options=activity_options, index=activity_index)

            diet_value = ""
            if profile.dietary_restrictions:
                diet_value = profile.dietary_restrictions
            dietary_restrictions = st.text_input("Dietary Restrictions", value=diet_value)

            pref_value = ""
            if profile.preferences:
                pref_value = profile.preferences
            preferences = st.text_input("Workout Preferences", value=pref_value)

            if st.form_submit_button("Save"):
                profile_data = {}
                if age > 0:
                    profile_data['age'] = age
                if weight > 0:
                    profile_data['weight'] = weight
                if height > 0:
                    profile_data['height'] = height
                if fitness_goal:
                    profile_data['fitness_goal'] = fitness_goal
                if activity_level:
                    profile_data['activity_level'] = activity_level
                profile_data['dietary_restrictions'] = dietary_restrictions
                profile_data['preferences'] = preferences

                update_profile(st.session_state.user['id'], profile_data, db)
                st.success("Saved!")
                st.rerun()

    st.sidebar.write("---")

    # TODO: Clear chat should probably ask for confirmation first
    if st.sidebar.button("Clear Chat"):
        st.session_state.messages = []
        st.rerun()

    if st.sidebar.button("Logout"):
        st.session_state.user = None
        st.session_state.messages = []
        st.rerun()

    # Main chat area
    st.title("Fitness Coach AI")

    if len(st.session_state.messages) == 0:
        messages = load_conversation_history(st.session_state.user['id'], db)
        st.session_state.messages = messages

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    prompt = st.chat_input("Ask me anything about fitness...")
    if prompt:
        save_message(st.session_state.user['id'], "user", prompt, db)
        st.session_state.messages.append({"role": "user", "content": prompt, "timestamp": datetime.utcnow()})

        with st.chat_message("user"):
            st.write(prompt)

        # Get agent response
        # TODO: Add streaming response instead of waiting for full response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                user_data = get_user_data(st.session_state.user['id'], db)
                agent = FitnessCoachAgent(user_data, st.session_state.messages)
                response = agent.chat(prompt)
                st.write(response)

        # Save assistant message
        save_message(st.session_state.user['id'], "assistant", response, db)
        st.session_state.messages.append({"role": "assistant", "content": response, "timestamp": datetime.utcnow()})

    db.close()

def main():
    if st.session_state.user is None:
        auth_view()
    else:
        chat_page()

if __name__ == "__main__":
    main()