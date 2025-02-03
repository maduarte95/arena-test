import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import hashlib
from db_manager import GameDataManager

def user_login() -> bool:
    """Handle user login"""
    if 'username' not in st.session_state:
        st.sidebar.title("Login")
        with st.sidebar.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login")
            
            if submitted:
                # Hash password
                password_hash = hashlib.sha256(password.encode()).hexdigest()
                
                # Check user
                user = st.session_state.db_manager.get_user(username)
                if user and user['password_hash'] == password_hash:
                    st.session_state.username = username
                    st.rerun()
                else:
                    st.sidebar.error("Invalid username or password")
        
        # Registration form
        st.sidebar.title("Register")
        with st.sidebar.form("register_form"):
            new_username = st.text_input("Choose Username")
            new_password = st.text_input("Choose Password", type="password")
            confirm_password = st.text_input("Confirm Password", type="password")
            submitted = st.form_submit_button("Register")
            
            if submitted:
                if new_password != confirm_password:
                    st.sidebar.error("Passwords don't match")
                elif len(new_password) < 6:
                    st.sidebar.error("Password must be at least 6 characters")
                else:
                    password_hash = hashlib.sha256(new_password.encode()).hexdigest()
                    if st.session_state.db_manager.create_user(new_username, password_hash):
                        st.sidebar.success("Registration successful! Please login.")
                    else:
                        st.sidebar.error("Username already exists")
        
        return False
    return True

def calculate_win_statistics(games_df):
    """Calculate win statistics for players"""
    total_games = len(games_df)
    wins = games_df['winner'].value_counts()
    win_rates = (wins / total_games * 100).round(1)
    
    stats_df = pd.DataFrame({
        'Player': wins.index,
        'Wins': wins.values,
        'Win Rate (%)': win_rates.values
    })
    
    # Add total games played
    stats_df['Games Played'] = total_games
    
    return stats_df

def render_analysis_ui():

    if 'db_manager' not in st.session_state:
        try:
            st.session_state.db_manager = GameDataManager()
        except ValueError as e:
            st.error(f"Database connection error: {e}")
            st.stop()

    st.title("Game Analysis Dashboard")
    
    # Handle login/registration
    if not user_login():
        return
    
    # Get all games
    recent_games = st.session_state.db_manager.get_recent_games(limit=50)
    if not recent_games:
        st.warning("No games found in the database.")
        return
        
    # Convert to DataFrame for easier manipulation
    games_df = pd.DataFrame(recent_games)
    games_df['created_at'] = pd.to_datetime(games_df['created_at'])
    
    # Create tabs for different views
    tab1, tab2, tab3 = st.tabs(["Global Statistics", "User Statistics", "Game Analysis"])
    
    with tab1:
        st.header("Global Statistics")
        
        # Overview metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Games", len(games_df))
        with col2:
            completed_games = len(games_df[games_df['status'] == 'completed'])
            st.metric("Completed Games", completed_games)
        with col3:
            avg_turns = games_df['total_turns'].mean()
            st.metric("Average Turns per Game", f"{avg_turns:.1f}")
        
        # Win Statistics
        st.subheader("Win Statistics")
        stats_df = calculate_win_statistics(games_df)
        
        # Display win statistics
        st.dataframe(stats_df, hide_index=True)
        
        # Win rate visualization
        fig = px.pie(stats_df, 
                    values='Wins', 
                    names='Player',
                    title='Win Distribution',
                    hole=0.4)
        st.plotly_chart(fig)
        
        # Games over time
        st.subheader("Games Over Time")
        games_df['date'] = games_df['created_at'].dt.date
        games_by_date = games_df.groupby('date').size().reset_index(name='count')
        fig = px.line(games_by_date, 
                     x='date', 
                     y='count',
                     title='Number of Games Played Over Time')
        st.plotly_chart(fig)
    
    with tab2:
        st.header("User Statistics")
        
        # Get user stats
        user_stats = pd.DataFrame(st.session_state.db_manager.get_user_stats())
        if not user_stats.empty:
            # Calculate win rates
            user_stats['win_rate'] = (user_stats['games_won'] / 
                                    user_stats['games_played'] * 100).round(1)
            user_stats['win_rate'] = user_stats['win_rate'].fillna(0)
            
            # Sort by win rate
            user_stats = user_stats.sort_values('win_rate', ascending=False)
            
            # Display leaderboard
            st.subheader("Player Leaderboard")
            st.dataframe(
                user_stats[[
                    'username', 'games_played', 'games_won', 'win_rate'
                ]].rename(columns={
                    'username': 'Player',
                    'games_played': 'Games Played',
                    'games_won': 'Wins',
                    'win_rate': 'Win Rate (%)'
                }),
                hide_index=True
            )
            
            # Current user stats
            if 'username' in st.session_state:
                st.subheader("Your Statistics")
                user_row = user_stats[user_stats['username'] == st.session_state.username].iloc[0]
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Games Played", user_row['games_played'])
                with col2:
                    st.metric("Wins", user_row['games_won'])
                with col3:
                    st.metric("Win Rate", f"{user_row['win_rate']}%")
    
    with tab3:
        st.header("Game Analysis")
        
        # Game selection
        selected_game_id = st.selectbox(
            "Select a game to analyze",
            options=games_df['_id'].tolist(),
            format_func=lambda x: f"Game {x} ({games_df[games_df['_id']==x]['created_at'].iloc[0].strftime('%Y-%m-%d %H:%M')})"
        )
        
        if selected_game_id:
            game_history = st.session_state.db_manager.get_game_history(selected_game_id)
            
            if game_history:
                game_tab1, game_tab2, game_tab3, game_tab4 = st.tabs([
                    "Game Summary", "Conversations", "HP Analysis", "Position Tracking"
                ])
                
                with game_tab1:
                    st.subheader("Game Information")
                    game_info = game_history['game_info']
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write("Status:", game_info['status'])
                        st.write("Winner:", game_info.get('winner', 'N/A'))
                        st.write("Total Turns:", game_info['total_turns'])
                        if 'player_a_username' in game_info:
                            st.write("Player:", game_info['player_a_username'])
                    with col2:
                        st.write("Start Time:", game_info['created_at'])
                        if 'end_time' in game_info:
                            st.write("End Time:", game_info['end_time'])
                    
                    if game_info['status'] == 'completed' and game_info.get('final_state'):
                        st.markdown("### Final Game State")
                        st.json(game_info['final_state'])
                
                with game_tab2:
                    st.subheader("Conversation History")
                    for conv in game_history['conversations']:
                        st.markdown(f"### Turn {conv['turn_number']}")
                        
                        # Show messages
                        for msg in conv['messages']:
                            if isinstance(msg, dict):
                                st.markdown(f"**{msg.get('role', 'Unknown')}**:")
                                st.write(msg.get('content', 'No content'))
                                if 'player' in msg:
                                    st.write(f"Player: {msg['player']}")
                        
                        # Show LLM parameters if available
                        if 'llm_params' in conv:
                            st.markdown("#### LLM Parameters")
                            st.json(conv['llm_params'])
                        
                        st.markdown("---")
                
                with game_tab3:
                    st.subheader("HP Changes Over Time")
                    # Extract HP data from turns
                    hp_data = []
                    for turn in game_history['turns']:
                        state = turn['player_state']
                        hp_data.append({
                            'turn': turn['turn_number'],
                            'Player A': state['player_a']['hp'],
                            'Player B': state['player_b']['hp']
                        })
                    
                    hp_df = pd.DataFrame(hp_data)
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=hp_df['turn'], y=hp_df['Player A'],
                                           name='Player A', mode='lines+markers'))
                    fig.add_trace(go.Scatter(x=hp_df['turn'], y=hp_df['Player B'],
                                           name='Player B', mode='lines+markers'))
                    fig.update_layout(title='HP Progression',
                                    xaxis_title='Turn',
                                    yaxis_title='HP')
                    st.plotly_chart(fig)
                
                with game_tab4:
                    st.subheader("Position Changes")
                    # Extract position data
                    pos_data = []
                    for turn in game_history['turns']:
                        state = turn['player_state']
                        pos_data.append({
                            'turn': turn['turn_number'],
                            'Player A X': state['player_a']['position'][0],
                            'Player A Y': state['player_a']['position'][1],
                            'Player B X': state['player_b']['position'][0],
                            'Player B Y': state['player_b']['position'][1]
                        })
                    
                    pos_df = pd.DataFrame(pos_data)
                    fig = go.Figure()
                    
                    # Plot paths for both players
                    fig.add_trace(go.Scatter(
                        x=pos_df['Player A X'],
                        y=pos_df['Player A Y'],
                        name='Player A',
                        mode='lines+markers',
                        marker=dict(size=10, symbol='circle'),
                        line=dict(width=2, dash='solid')
                    ))
                    
                    fig.add_trace(go.Scatter(
                        x=pos_df['Player B X'],
                        y=pos_df['Player B Y'],
                        name='Player B',
                        mode='lines+markers',
                        marker=dict(size=10, symbol='square'),
                        line=dict(width=2, dash='dash')
                    ))
                    
                    fig.update_layout(
                        title='Player Positions',
                        xaxis=dict(range=[-1, 10], title='X Position'),
                        yaxis=dict(range=[-1, 10], title='Y Position'),
                        showlegend=True
                    )
                    
                    st.plotly_chart(fig)