"""
ITBP RTC Grain Shop Management System
Streamlit Frontend - Main Application
"""
import streamlit as st
from streamlit_option_menu import option_menu
import requests
import os
from dotenv import load_dotenv

load_dotenv()

# Configuration
API_BASE_URL = os.getenv('API_BASE_URL', 'http://localhost:5001/api')

# Page config
st.set_page_config(
    page_title="ITBP RTC - Grain Shop Management",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="auto"
)

# Custom CSS
st.markdown("""
<style>
    /* Main container */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    
    /* Hide Streamlit's auto-generated page navigation */
    [data-testid="stSidebarNav"] { display: none !important; }
    div[data-testid="stSidebarNavItems"] { display: none !important; }
    ul[data-testid="stSidebarNavItems"] { display: none !important; }
    
    /* Header styling */
    .main-header {
        background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        margin-bottom: 2rem;
        color: white;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    
    .main-header h1 {
        margin: 0;
        font-size: 1.8rem;
        font-weight: 600;
    }
    
    .main-header p {
        margin: 0.5rem 0 0 0;
        opacity: 0.9;
        font-size: 0.95rem;
    }
    
    /* Card styling */
    .stat-card {
        background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%);
        padding: 1.5rem;
        border-radius: 12px;
        border: 1px solid #e0e5ec;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        text-align: center;
        transition: transform 0.2s, box-shadow 0.2s;
    }
    
    .stat-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    
    .stat-value {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1e3a5f;
        line-height: 1;
    }
    
    .stat-label {
        font-size: 0.9rem;
        color: #6c757d;
        margin-top: 0.5rem;
        font-weight: 500;
    }
    
    /* Sidebar styling */
    .css-1d391kg {
        background: linear-gradient(180deg, #1e3a5f 0%, #2d5a87 100%);
    }
    
    /* Button styling */
    .stButton>button {
        background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.5rem 1.5rem;
        font-weight: 500;
        transition: all 0.3s;
    }
    
    .stButton>button:hover {
        background: linear-gradient(135deg, #2d5a87 0%, #3d7ab7 100%);
        box-shadow: 0 4px 12px rgba(30, 58, 95, 0.3);
    }
    
    /* Success/warning/error badges */
    .badge-success {
        background-color: #28a745;
        color: white;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 500;
    }
    
    .badge-warning {
        background-color: #ffc107;
        color: #212529;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 500;
    }
    
    .badge-danger {
        background-color: #dc3545;
        color: white;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 500;
    }
    
    /* Table styling */
    .dataframe {
        border-radius: 8px;
        overflow: hidden;
    }
    
    /* Form styling */
    .stTextInput>div>div>input,
    .stSelectbox>div>div>div,
    .stNumberInput>div>div>input {
        border-radius: 8px;
    }
    
    /* Info cards */
    .info-card {
        background: #e8f4fd;
        border-left: 4px solid #2d5a87;
        padding: 1rem;
        border-radius: 0 8px 8px 0;
        margin: 1rem 0;
    }
    
    /* Category badges */
    .category-veg {
        background-color: #28a745;
        color: white;
        padding: 0.2rem 0.6rem;
        border-radius: 4px;
        font-size: 0.75rem;
    }
    
    .category-non_veg {
        background-color: #dc3545;
        color: white;
        padding: 0.2rem 0.6rem;
        border-radius: 4px;
        font-size: 0.75rem;
    }
    
    .category-grocery {
        background-color: #fd7e14;
        color: white;
        padding: 0.2rem 0.6rem;
        border-radius: 4px;
        font-size: 0.75rem;
    }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """Initialize session state variables"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user' not in st.session_state:
        st.session_state.user = None
    if 'token' not in st.session_state:
        st.session_state.token = None


def api_request(method, endpoint, data=None, params=None):
    """Make API request with authentication"""
    headers = {}
    if st.session_state.token:
        headers['Authorization'] = f'Bearer {st.session_state.token}'
    
    url = f"{API_BASE_URL}{endpoint}"
    
    try:
        if method == 'GET':
            response = requests.get(url, headers=headers, params=params, timeout=10)
        elif method == 'POST':
            response = requests.post(url, headers=headers, json=data, timeout=10)
        elif method == 'PUT':
            response = requests.put(url, headers=headers, json=data, timeout=10)
        elif method == 'DELETE':
            response = requests.delete(url, headers=headers, timeout=10)
        else:
            return None, "Invalid method"
        
        if response.status_code == 401:
            # For login endpoint, return the actual error message (e.g. "Invalid credentials")
            # instead of the generic "session expired" message
            if '/auth/login' in endpoint:
                try:
                    error_data = response.json()
                    return error_data, None
                except ValueError:
                    return None, "Invalid credentials"
            # For all other endpoints, treat 401 as session expired
            st.session_state.authenticated = False
            st.session_state.user = None
            st.session_state.token = None
            return None, "Session expired. Please login again."
        
        # Try to parse JSON; handle non-JSON responses (e.g. HTML error pages)
        try:
            return response.json(), None
        except ValueError:
            return None, f"Server error (HTTP {response.status_code}). The API may be unable to reach the database."
    except requests.exceptions.ConnectionError:
        return None, "Cannot connect to server. Please ensure the API is running."
    except Exception as e:
        return None, str(e)


def login_page():
    """Display login page"""
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("""
        <div style="text-align: center; padding: 2rem 0;">
            <h1 style="color: #1e3a5f; font-size: 2.5rem;">🌾 ITBP RTC</h1>
            <h2 style="color: #2d5a87; font-weight: 400;">Grain Shop Management System</h2>
        </div>
        """, unsafe_allow_html=True)
        
        with st.form("login_form"):
            st.subheader("Login")
            username = st.text_input("Username", placeholder="Enter your username")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            
            col_a, col_b, col_c = st.columns([1, 2, 1])
            with col_b:
                submitted = st.form_submit_button("🔐 Login", use_container_width=True)
            
            if submitted:
                if not username or not password:
                    st.error("Please enter both username and password")
                else:
                    with st.spinner("Authenticating..."):
                        response, error = api_request('POST', '/auth/login', {
                            'username': username,
                            'password': password
                        })
                        
                        if error:
                            st.error(error)
                        elif response and response.get('status') == 'success':
                            st.session_state.authenticated = True
                            st.session_state.user = response['data']['user']
                            st.session_state.token = response['data']['access_token']
                            st.success("Login successful!")
                            st.rerun()
                        else:
                            st.error(response.get('error', 'Login failed'))


def logout():
    """Handle logout"""
    api_request('POST', '/auth/logout')
    st.session_state.authenticated = False
    st.session_state.user = None
    st.session_state.token = None
    st.rerun()


def main():
    """Main application"""
    init_session_state()
    
    if not st.session_state.authenticated:
        # Hide sidebar completely on login page
        st.markdown("""
        <style>
            [data-testid="stSidebar"] { display: none; }
            [data-testid="stSidebarCollapsedControl"] { display: none; }
            [data-testid="collapsedControl"] { display: none; }
            header [data-testid="stSidebarNavItems"] { display: none; }
            #MainMenu { visibility: hidden; }
            section[data-testid="stSidebar"] { display: none; }
        </style>
        """, unsafe_allow_html=True)
        login_page()
        return
    
    user = st.session_state.user
    role = user.get('role', '')
    
    # Sidebar
    with st.sidebar:
        st.markdown(f"""
        <div style="padding: 1rem; text-align: center;">
            <h3 style="color: #1e3a5f; margin-bottom: 0.5rem;">👤 {user.get('full_name', 'User')}</h3>
            <p style="color: #6c757d; font-size: 0.85rem; margin: 0;">
                {role.replace('_', ' ').title()}
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        st.divider()
        
        # Menu based on role
        if role == 'admin':
            menu_options = [
                "Dashboard",
                "Demand Management",
                "User Management",
                "Contractor Management",
                "Mess Management",
                "Items Management",
                "Grain Shop",
                "Supply Management",
                "Distribution",
                "Price Changes",
                "Approvals",
                "Reports"
            ]
            menu_icons = ['speedometer2', 'clipboard-check', 'people', 'building', 'shop', 'box-seam', 
                         'basket3', 'truck', 'arrow-left-right', 'currency-dollar', 'check2-circle', 'graph-up']
        elif role == 'grain_shop_user':
            menu_options = [
                "Dashboard",
                "Demand Management",
                "Grain Shop Inventory",
                "Supply Management",
                "Distribution",
                "Price Changes",
                "Contractors"
            ]
            menu_icons = ['speedometer2', 'clipboard-check', 'basket3', 'truck', 'arrow-left-right', 'currency-dollar', 'building']
        elif role == 'contractor':
            menu_options = [
                "Dashboard",
                "Demand Management"
            ]
            menu_icons = ['speedometer2', 'clipboard-check']
        else:  # mess_user
            menu_options = [
                "Dashboard",
                "Demand Management",
                "Mess Inventory",
                "Daily Usage"
            ]
            menu_icons = ['speedometer2', 'clipboard-check', 'box-seam', 'calendar-check']
        
        selected = option_menu(
            menu_title=None,
            options=menu_options,
            icons=menu_icons,
            default_index=0,
            styles={
                "container": {"padding": "0"},
                "icon": {"font-size": "1rem"},
                "nav-link": {
                    "font-size": "0.9rem",
                    "text-align": "left",
                    "margin": "0.2rem 0",
                    "padding": "0.7rem 1rem",
                    "border-radius": "8px"
                },
                "nav-link-selected": {
                    "background-color": "#1e3a5f",
                    "font-weight": "500"
                }
            }
        )
        
        st.divider()
        
        if st.button("🚪 Logout", use_container_width=True):
            logout()
    
    # Main content area
    st.markdown("""
    <div class="main-header">
        <h1>🌾 ITBP RTC - Grain Shop Management</h1>
        <p>Indo-Tibetan Border Police - Recruit Training Centre</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Route to appropriate page
    # Add the frontend directory to sys.path for correct imports
    import sys, os, importlib
    frontend_dir = os.path.dirname(os.path.abspath(__file__))
    if frontend_dir not in sys.path:
        sys.path.insert(0, frontend_dir)
    
    if selected == "Dashboard":
        from pages import dashboard
        importlib.reload(dashboard)
        dashboard.show(api_request, user)
    elif selected == "Demand Management":
        from pages import demand_management
        importlib.reload(demand_management)
        demand_management.show(api_request, user)
    elif selected == "User Management":
        from pages import users
        importlib.reload(users)
        users.show(api_request)
    elif selected == "Contractor Management" or selected == "Contractors":
        from pages import contractors
        importlib.reload(contractors)
        contractors.show(api_request, user)
    elif selected == "Mess Management":
        from pages import mess_management
        importlib.reload(mess_management)
        mess_management.show(api_request)
    elif selected == "Items Management":
        from pages import items
        importlib.reload(items)
        items.show(api_request)
    elif selected == "Grain Shop" or selected == "Grain Shop Inventory":
        from pages import grain_shop
        importlib.reload(grain_shop)
        grain_shop.show(api_request, user)
    elif selected == "Supply Management":
        from pages import supply_management
        importlib.reload(supply_management)
        supply_management.show(api_request, user)
    elif selected == "Distribution":
        from pages import distribution
        importlib.reload(distribution)
        distribution.show(api_request, user)
    elif selected == "Price Changes":
        from pages import price_changes
        importlib.reload(price_changes)
        price_changes.show(api_request, user)
    elif selected == "Approvals":
        from pages import approvals
        importlib.reload(approvals)
        approvals.show(api_request)
    elif selected == "Reports":
        from pages import reports
        importlib.reload(reports)
        reports.show(api_request)
    elif selected == "Mess Inventory":
        from pages import mess_inventory
        importlib.reload(mess_inventory)
        mess_inventory.show(api_request, user)
    elif selected == "Daily Usage":
        from pages import daily_usage
        importlib.reload(daily_usage)
        daily_usage.show(api_request, user)


if __name__ == "__main__":
    main()
