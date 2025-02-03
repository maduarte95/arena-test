import streamlit as st
from db_manager import GameDataManager
import hashlib
from datetime import datetime

class AuthManager:
    def __init__(self, db_manager: GameDataManager):
        self.db = db_manager
        
    def hash_password(self, password: str) -> str:
        """Create a hash of the password"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def create_user(self, username: str, password: str) -> bool:
        """Create a new user"""
        # Check if user exists
        existing_user = self.db.db.users.find_one({'username': username})
        if existing_user:
            return False
            
        # Create new user
        user_doc = {
            'username': username,
            'password_hash': self.hash_password(password),
            'created_at': datetime.utcnow(),
            'games_played': 0,
            'games_won': 0
        }
        
        self.db.db.users.insert_one(user_doc)
        return True
    
    def verify_user(self, username: str, password: str) -> bool:
        """Verify user credentials"""
        user = self.db.db.users.find_one({
            'username': username,
            'password_hash': self.hash_password(password)
        })
        return user is not None
    
    def update_user_stats(self, username: str, won: bool):
        """Update user statistics after a game"""
        update = {
            '$inc': {
                'games_played': 1,
                'games_won': 1 if won else 0
            }
        }
        self.db.db.users.update_one({'username': username}, update)
    
    def get_user_stats(self, username: str) -> dict:
        """Get user statistics"""
        user = self.db.db.users.find_one({'username': username})
        if not user:
            return None
            
        return {
            'username': user['username'],
            'games_played': user['games_played'],
            'games_won': user['games_won'],
            'win_rate': (user['games_won'] / user['games_played'] * 100) if user['games_played'] > 0 else 0
        }

def render_auth_ui():
    """Render the authentication UI"""
    st.title("AI Arena - Login")
    
    # Initialize AuthManager
    if 'auth_manager' not in st.session_state:
        st.session_state.auth_manager = AuthManager(st.session_state.db_manager)
    
    # Check if user is logged in
    if 'username' not in st.session_state:
        tab1, tab2 = st.tabs(["Login", "Register"])
        
        with tab1:
            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                submit = st.form_submit_button("Login")
                
                if submit:
                    if st.session_state.auth_manager.verify_user(username, password):
                        st.session_state.username = username
                        st.rerun()
                    else:
                        st.error("Invalid username or password")
        
        with tab2:
            with st.form("register_form"):
                new_username = st.text_input("Choose Username")
                new_password = st.text_input("Choose Password", type="password")
                confirm_password = st.text_input("Confirm Password", type="password")
                submit = st.form_submit_button("Register")
                
                if submit:
                    if new_password != confirm_password:
                        st.error("Passwords don't match")
                    elif len(new_password) < 6:
                        st.error("Password must be at least 6 characters")
                    else:
                        if st.session_state.auth_manager.create_user(new_username, new_password):
                            st.success("Registration successful! Please login.")
                        else:
                            st.error("Username already exists")
        
        return False
    
    return True