import streamlit as st
from agent import GameMaster
from game_state import GameState, PlayerType
from player_b import PlayerBAgent
from narrator import GameNarrator
from config import get_api_key
import asyncio
import streamlit.components.v1 as components
import json
from prompt_manager import PromptManager, Prompt, PromptType
import streamlit as st
from db_manager import GameDataManager
from analysis import render_analysis_ui
from auth import render_auth_ui

def initialize_session_state():
    if 'game_state' not in st.session_state:
        st.session_state.game_state = GameState()
    if 'game_master_a' not in st.session_state:
        try:
            api_key = get_api_key()
            st.session_state.game_master_a = GameMaster("Player A", api_key)
            st.session_state.player_b = PlayerBAgent(api_key)
            st.session_state.narrator = GameNarrator(api_key)
        except ValueError as e:
            st.error(f"Configuration error: {e}")
            st.stop()
    if 'conversation_turns' not in st.session_state:
        st.session_state.conversation_turns = 0
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    if 'total_turns' not in st.session_state:
        st.session_state.total_turns = 0

    # Create new game session with username if logged in and game_id not set
    if 'game_id' not in st.session_state:
        username = st.session_state.get('username')  # Will be None if not logged in
        game_id = st.session_state.db_manager.create_game_session(
            st.session_state.game_state.to_dict(),
            username  # This will be None if user isn't logged in
        )
        st.session_state.game_id = game_id

def initialize_prompt_manager():
    if 'prompt_manager' not in st.session_state:
        st.session_state.prompt_manager = PromptManager()
    if 'selected_prompts' not in st.session_state:
        # Initialize with default prompt names for all types
        st.session_state.selected_prompts = {
            PromptType.GAME_MASTER: "Default Game Master",
            PromptType.PLAYER_B: "Default Player B",
            PromptType.NARRATOR: "Default Narrator" 
        }

    # Ensure prompts are loaded
    if not hasattr(st.session_state.prompt_manager, 'prompts'):
        st.session_state.prompt_manager.load_prompts()

def render_prompt_management():
    st.sidebar.title("Prompt Management")
    
    # Prompt selection for each type
    for prompt_type in PromptType:
        st.sidebar.subheader(f"{prompt_type.value.title()} Prompts")
        prompts = st.session_state.prompt_manager.get_prompts(prompt_type)
        prompt_names = [p.name for p in prompts]
        
        selected = st.sidebar.selectbox(
            f"Select {prompt_type.value} prompt",
            prompt_names,
            key=f"select_{prompt_type.value}",
            index=prompt_names.index(st.session_state.selected_prompts[prompt_type])
        )
        st.session_state.selected_prompts[prompt_type] = selected
        
        # Show current prompt content
        with st.sidebar.expander(f"View {prompt_type.value} prompt"):
            selected_prompt = st.session_state.prompt_manager.get_prompt(prompt_type, selected)
            st.text_area(
                "Prompt content",
                selected_prompt.content,
                height=200,
                key=f"content_{prompt_type.value}",
                disabled=True
            )

    # Add new prompt button
    if st.sidebar.button("Add New Prompt"):
        st.sidebar.markdown("### Add New Prompt")
        prompt_type = st.sidebar.selectbox(
            "Prompt type",
            [pt.value for pt in PromptType]
        )
        name = st.sidebar.text_input("Prompt name")
        description = st.sidebar.text_input("Description")
        content = st.sidebar.text_area("Content")
        
        if st.sidebar.button("Save Prompt"):
            new_prompt = Prompt(
                name=name,
                content=content,
                description=description,
                type=PromptType(prompt_type)
            )
            st.session_state.prompt_manager.add_prompt(new_prompt)
            st.sidebar.success("Prompt added successfully!")
            st.rerun()

def render_chat_interface():
    for message in st.session_state.messages:
        if message["role"] == "user":
            with st.chat_message("user", avatar="👤"):
                st.markdown(message["content"])
        else:
            with st.chat_message("assistant", avatar="🎲"):
                st.markdown(message["content"])
    
    return st.empty()

async def process_player_a_turn(message: str, game_state: GameState, game_master: GameMaster, 
                              streaming_placeholder):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": message})
    
    # Show user message immediately
    with st.chat_message("user", avatar="👤"):
        st.markdown(message)
    
    # Show streaming response in a chat message container
    with st.chat_message("assistant", avatar="🎲"):
        message_placeholder = st.empty()
        
        def update_stream(text):
            narrative = text.split('###Updates')[0].strip() if '###Updates' in text else text
            message_placeholder.markdown(narrative)
        
        # Process the message with streaming
        response, updates = await game_master.process_turn_streaming(
            message,
            game_state.to_dict(),
            update_stream
        )
        
        # Update with final response
        message_placeholder.markdown(response)
    
    # Add GM response to message history
    st.session_state.messages.append({"role": "assistant", "content": response})
    
    # Get the narrative part
    narrative = response.split('###Updates')[0].strip()
    
    # Update game state
    game_state.update_state(
        updates=updates,
        player=PlayerType.A,
        narrative=narrative
    )

    # Save turn data
    turn_data = {
        'game_state': game_state.to_dict(),
        'conversation': {
            'player_message': message,
            'gm_response': response
        },
        'actions': updates
    }
    st.session_state.db_manager.save_turn_data(
        st.session_state.game_id, 
        turn_data
    )
    
    # Save LLM parameters for Player A
    st.session_state.db_manager.save_conversation(
        st.session_state.game_id,
        game_state.turn_number,
        st.session_state.messages,
        {
            'model': 'claude-3-sonnet-20240229',
            'prompts': {
                prompt_type.value: name  # Convert enum to string
                for prompt_type, name in st.session_state.selected_prompts.items()
            }
        }
    )
    
    return narrative

async def process_player_b_turn(game_state: GameState, player_b: PlayerBAgent):
    """Process Player B's turn (AI-simulated)"""
    recent_actions = game_state.get_recent_actions()
    
    # Generate Player B's response
    narrative, updates = await player_b.generate_turn(
        game_state.to_dict(),
        str(recent_actions)
    )
    
    # Save Player B's turn data
    turn_data = {
        'game_state': game_state.to_dict(),
        'conversation': {
            'player': 'B',
            'message': 'AI Generated Turn',
            'narrative': narrative,
            'updates': updates
        },
        'actions': updates
    }
    st.session_state.db_manager.save_turn_data(
        st.session_state.game_id, 
        turn_data
    )
    
    # Save LLM parameters for Player B
    st.session_state.db_manager.save_conversation(
        st.session_state.game_id,
        game_state.turn_number,
        [{
            'role': 'assistant',
            'content': narrative,
            'player': 'B'
        }],
        {
            'model': 'claude-3-sonnet-20240229',
            'prompts': {
                PromptType.PLAYER_B.value: st.session_state.selected_prompts[PromptType.PLAYER_B]
            }
        }
    )

    # Update game state
    game_state.update_state(
        updates=updates,
        player=PlayerType.B,
        narrative=narrative
    )
    
    return narrative

async def update_narrative_summary(game_state: GameState, narrator: GameNarrator):
    """Generate and update the narrative summary"""
    recent_actions = game_state.get_recent_actions()
    summary = await narrator.generate_turn_summary(
        recent_actions,
        game_state.to_dict()
    )
    
    # Save narrator's summary
    st.session_state.db_manager.save_conversation(
        st.session_state.game_id,
        game_state.turn_number,
        [{
            'role': 'narrator',
            'content': summary
        }],
        {
            'model': 'claude-3-sonnet-20240229',
            'prompts': {
                PromptType.NARRATOR.value: st.session_state.selected_prompts[PromptType.NARRATOR]
                }
        }
    )
    
    game_state.public_narrative.append(summary)
    return summary

def create_grid_display(game_state):
    grid_html = """
    <style>
        .grid-container {
            display: grid;
            grid-template-columns: repeat(10, 40px);
            gap: 2px;
            background-color: #f0f0f0;
            padding: 10px;
            border-radius: 8px;
            margin: 0 auto;
        }
        .grid-cell {
            width: 40px;
            height: 40px;
            background-color: white;
            border: 1px solid #ddd;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
            transition: all 0.2s ease;
        }
        .grid-cell:hover {
            background-color: #f8f8f8;
            transform: scale(1.05);
        }
        .coordinates {
            color: #ccc;
            font-size: 12px;
            font-family: monospace;
        }
    </style>
    <div class="grid-container">
    """
    
    player_a_pos = game_state.player_a.position
    player_b_pos = game_state.player_b.position
    
    for y in range(10):
        for x in range(10):
            if (x, y) == player_a_pos:
                cell_content = "🔵"
            elif (x, y) == player_b_pos:
                cell_content = "🔴"
            else:
                cell_content = f'<span class="coordinates">{x},{y}</span>'
                
            grid_html += f'<div class="grid-cell">{cell_content}</div>'
    
    grid_html += "</div>"
    
    components.html(grid_html, height=500)

def check_game_end(game_state: GameState) -> bool:
    """Returns True if game has ended, saves final state to database"""
    game_over = False
    winner = None
    
    if game_state.player_a.hp <= 0:
        game_over = True
        winner = "Player B"
    elif game_state.player_b.hp <= 0:
        game_over = True
        winner = "Player A"
    elif st.session_state.total_turns >= 3:
        game_over = True
        # Determine winner based on remaining HP if turns are maxed
        if game_state.player_a.hp > game_state.player_b.hp:
            winner = "Player A"
        elif game_state.player_b.hp > game_state.player_a.hp:
            winner = "Player B"
        else:
            winner = "Draw"

    if game_over:
        # Save final game state and winner
        st.session_state.db_manager.end_game(
            st.session_state.game_id,
            winner,
            game_state.to_dict()
        )
        return True
    return False

def render_game_ui():

    # Initialize db_manager first
    if 'db_manager' not in st.session_state:
        try:
            st.session_state.db_manager = GameDataManager()
        except ValueError as e:
            st.error(f"Database connection error: {e}")
            st.stop()

    # Check authentication
    if not render_auth_ui():
        return
    
    st.title(f"AI Arena - Welcome, {st.session_state.username}!")
    initialize_session_state()
    initialize_prompt_manager()
    
    # Add prompt management UI
    render_prompt_management()

    # Display the grid
    st.markdown("### Battle Arena")
    create_grid_display(st.session_state.game_state)
    
    # Display narrative summary
    if st.session_state.game_state.public_narrative:
        st.markdown("### Game Summary")
        with st.container():
            st.markdown(st.session_state.game_state.public_narrative[-1])
            if len(st.session_state.game_state.public_narrative) > 1:
                with st.expander("Previous Events"):
                    for i, narrative in enumerate(st.session_state.game_state.public_narrative[:-1]):
                        st.markdown(f"Turn {i + 1}:")
                        st.markdown(narrative)
    
    # Game state display
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Player A")
        st.write(f"HP: {st.session_state.game_state.player_a.hp}")
        st.write(f"Position: {st.session_state.game_state.player_a.position}")
        if st.session_state.game_state.player_a.custom_stats:
            st.write("Custom stats:", st.session_state.game_state.player_a.custom_stats)
                        
    with col2:
        st.subheader("Player B (AI)")
        st.write(f"HP: {st.session_state.game_state.player_b.hp}")
        st.write(f"Position: {st.session_state.game_state.player_b.position}")
        if st.session_state.game_state.player_b.custom_stats:
            st.write("Custom stats:", st.session_state.game_state.player_b.custom_stats)
    
    # Check for game end
    if check_game_end(st.session_state.game_state):
        st.markdown("### Game Over!")
        winner = None
        if st.session_state.game_state.player_a.hp <= 0:
            winner = "Player B"
        elif st.session_state.game_state.player_b.hp <= 0:
            winner = "Player A"
        if winner:
            st.markdown(f"🏆 {winner} wins!")
        else:
            st.markdown("Game completed! Maximum turns reached.")
        return

    # Render chat interface
    streaming_placeholder = render_chat_interface()
    
    # Input area
    if st.session_state.conversation_turns < 5:
        if prompt := st.chat_input("Your message to the Game Master:"):
            # Process message
            response = asyncio.run(process_player_a_turn(
                prompt,
                st.session_state.game_state,
                st.session_state.game_master_a,
                streaming_placeholder
            ))
            
            st.session_state.conversation_turns += 1
            
            # If this was the 5th turn, process Player B's turn and update narrative
            if st.session_state.conversation_turns == 5:
                player_b_narrative = asyncio.run(process_player_b_turn(
                    st.session_state.game_state,
                    st.session_state.player_b
                ))
                
                # Generate narrative summary
                summary = asyncio.run(update_narrative_summary(
                    st.session_state.game_state,
                    st.session_state.narrator
                ))
                
                # Reset conversation turns for next round
                st.session_state.conversation_turns = 0
                st.session_state.total_turns += 1
                st.rerun()

# if __name__ == "__main__":
#     render_game_ui()

if __name__ == "__main__":
    pages = {
        "Game": render_game_ui,
        "Analysis": render_analysis_ui
    }
    page = st.sidebar.selectbox("Choose a page", list(pages.keys()))
    pages[page]()