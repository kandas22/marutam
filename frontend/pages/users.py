"""User Management Page - Admin Only"""
import streamlit as st
import pandas as pd


def show(api_request):
    """Display user management interface"""
    st.subheader("👥 User Management")
    
    tab1, tab2 = st.tabs(["📋 All Users", "➕ Create User"])
    
    with tab1:
        show_users_list(api_request)
    
    with tab2:
        show_create_user_form(api_request)


def show_users_list(api_request):
    """Display list of all users"""
    # Filters
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        search = st.text_input("🔍 Search", placeholder="Search by name, username or phone")
    
    with col2:
        role_filter = st.selectbox("Filter by Role", 
                                   ["All", "mess_user", "grain_shop_user", "admin"])
    
    with col3:
        st.write("")
        st.write("")
        refresh = st.button("🔄 Refresh")
    
    # Fetch users
    params = {}
    if search:
        params['search'] = search
    if role_filter != "All":
        params['role'] = role_filter
    
    response, error = api_request('GET', '/users', params=params)
    
    if error:
        st.error(error)
        return
    
    users = response.get('data', {}).get('users', []) if response else []
    
    if not users:
        st.info("No users found")
        return
    
    # Fetch managers for display (to resolve manager_id to names)
    managers_map = {}
    mgr_response, mgr_error = api_request('GET', '/users/managers')
    if mgr_response and mgr_response.get('data', {}).get('managers'):
        for mgr in mgr_response['data']['managers']:
            managers_map[mgr['id']] = mgr['full_name']
    
    # Display users table
    for user in users:
        with st.container():
            col1, col2, col3, col4, col5, col6 = st.columns([2.5, 2, 2, 2, 1, 2])
            
            with col1:
                st.write(f"**{user.get('full_name', 'N/A')}**")
                st.caption(f"👤 {user.get('username', 'N/A')}")
            
            with col2:
                st.write(f"📱 {user.get('phone', 'N/A')}")
                email = user.get('email')
                if email:
                    st.caption(f"✉️ {email}")
            
            with col3:
                role = user.get('role', '').replace('_', ' ').title()
                st.write(f"🏷️ {role}")
            
            with col4:
                manager_id = user.get('manager_id')
                if manager_id and manager_id in managers_map:
                    st.write(f"👔 {managers_map[manager_id]}")
                elif manager_id:
                    st.write(f"👔 Assigned")
                else:
                    st.caption("No manager")
            
            with col5:
                status = "🟢" if user.get('is_active') else "🔴"
                st.write(status)
            
            with col6:
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    if st.button("✏️", key=f"edit_{user['id']}", help="Edit"):
                        st.session_state.edit_user = user
                with col_b:
                    if st.button("🔑", key=f"pwd_{user['id']}", help="Reset Password"):
                        st.session_state.reset_pwd_user = user
                with col_c:
                    if user.get('role') != 'admin':
                        if st.button("🗑️", key=f"del_{user['id']}", help="Deactivate"):
                            if st.session_state.get(f"confirm_del_{user['id']}"):
                                delete_response, del_error = api_request('DELETE', f"/users/{user['id']}")
                                if del_error:
                                    st.error(del_error)
                                else:
                                    st.success("User deactivated")
                                    st.rerun()
                            else:
                                st.session_state[f"confirm_del_{user['id']}"] = True
                                st.warning("Click again to confirm")
            
            st.divider()
    
    # Edit dialog
    if 'edit_user' in st.session_state:
        show_edit_user_modal(api_request, st.session_state.edit_user)
    
    # Password reset dialog
    if 'reset_pwd_user' in st.session_state:
        show_reset_password_dialog(api_request, st.session_state.reset_pwd_user)


def show_create_user_form(api_request):
    """Form to create new user"""
    
    # Fetch available managers (admin users) for the dropdown
    managers = []
    mgr_response, mgr_error = api_request('GET', '/users/managers')
    if mgr_response and mgr_response.get('data', {}).get('managers'):
        managers = mgr_response['data']['managers']
    
    with st.form("create_user_form"):
        st.markdown("### Create New User")
        
        col1, col2 = st.columns(2)
        
        with col1:
            full_name = st.text_input("Full Name *", placeholder="Enter full name")
            username = st.text_input("Username *", placeholder="Enter username (for login)")
            phone = st.text_input("Phone Number *", placeholder="Enter phone number")
        
        with col2:
            role = st.selectbox("Role *", ["mess_user", "grain_shop_user"], 
                               format_func=lambda x: x.replace('_', ' ').title())
            email = st.text_input("Email (Optional)", placeholder="Enter email address")
            
            # Assign Manager dropdown
            manager_options = {"": "-- No Manager --"}
            for mgr in managers:
                manager_options[mgr['id']] = f"{mgr['full_name']} ({mgr['username']})"
            
            selected_manager = st.selectbox(
                "Assign Manager",
                options=list(manager_options.keys()),
                format_func=lambda x: manager_options[x],
                help="Assign an admin user as the manager for this user"
            )
        
        password = st.text_input("Password *", type="password", placeholder="Minimum 6 characters")
        confirm_password = st.text_input("Confirm Password *", type="password")
        
        submitted = st.form_submit_button("➕ Create User", use_container_width=True)
        
        if submitted:
            if not all([full_name, username, phone, role, password]):
                st.error("Please fill all required fields (Full Name, Username, Phone, Role, Password)")
            elif len(phone) < 10:
                st.error("Phone number must be at least 10 digits")
            elif len(password) < 6:
                st.error("Password must be at least 6 characters")
            elif password != confirm_password:
                st.error("Passwords do not match")
            else:
                user_data = {
                    'full_name': full_name,
                    'username': username,
                    'role': role,
                    'phone': phone,
                    'password': password
                }
                
                # Add optional fields
                if email:
                    user_data['email'] = email
                if selected_manager:
                    user_data['manager_id'] = selected_manager
                
                response, error = api_request('POST', '/users', data=user_data)
                
                if error:
                    st.error(error)
                elif response and response.get('status') == 'success':
                    st.success("User created successfully!")
                    st.balloons()
                else:
                    st.error(response.get('error', 'Failed to create user'))


@st.dialog("✏️ Edit User", width="large")
def show_edit_user_modal(api_request, user):
    """Dialog popup to edit user"""
    
    # Fetch available managers
    managers = []
    mgr_response, mgr_error = api_request('GET', '/users/managers')
    if mgr_response and mgr_response.get('data', {}).get('managers'):
        managers = mgr_response['data']['managers']
    
    st.markdown(f"**Editing:** {user.get('full_name', '')} (`{user.get('username', '')}`)")
    st.markdown(f"**Role:** {user.get('role', '').replace('_', ' ').title()}")
    st.divider()
    
    col1, col2 = st.columns(2)
    
    with col1:
        full_name = st.text_input("Full Name", value=user.get('full_name', ''))
        phone = st.text_input("Phone *", value=user.get('phone', '') or '')
    
    with col2:
        is_active = st.checkbox("Active", value=user.get('is_active', True))
        
        # Manager dropdown for edit
        manager_options = {"": "-- No Manager --"}
        for mgr in managers:
            manager_options[mgr['id']] = f"{mgr['full_name']} ({mgr['username']})"
        
        current_manager = user.get('manager_id', '') or ''
        manager_keys = list(manager_options.keys())
        default_idx = manager_keys.index(current_manager) if current_manager in manager_keys else 0
        
        selected_manager = st.selectbox(
            "Assign Manager",
            options=manager_keys,
            index=default_idx,
            format_func=lambda x: manager_options[x],
            key="edit_manager_dialog"
        )
    
    st.divider()
    col_a, col_b = st.columns(2)
    
    with col_a:
        if st.button("💾 Save Changes", use_container_width=True, type="primary"):
            if not phone:
                st.error("Phone number is required")
            else:
                update_data = {
                    'full_name': full_name,
                    'phone': phone,
                    'is_active': is_active,
                    'manager_id': selected_manager if selected_manager else None
                }
                
                response, error = api_request('PUT', f"/users/{user['id']}", data=update_data)
                
                if error:
                    st.error(error)
                elif response and response.get('status') == 'success':
                    st.success("User updated successfully!")
                    if 'edit_user' in st.session_state:
                        del st.session_state.edit_user
                    st.rerun()
                else:
                    st.error(response.get('error', 'Failed to update user'))
    
    with col_b:
        if st.button("❌ Cancel", use_container_width=True):
            if 'edit_user' in st.session_state:
                del st.session_state.edit_user
            st.rerun()


@st.dialog("🔑 Reset Password")
def show_reset_password_dialog(api_request, user):
    """Dialog popup to reset user password"""
    st.markdown(f"**User:** {user.get('full_name', '')} (`{user.get('username', '')}`)")
    st.markdown(f"**Role:** {user.get('role', '').replace('_', ' ').title()}")
    st.divider()
    
    st.warning("⚠️ This will change the password for this user. They will need to use the new password to log in.")
    
    new_password = st.text_input("New Password *", type="password", placeholder="Minimum 6 characters", key="new_pwd")
    confirm_password = st.text_input("Confirm Password *", type="password", placeholder="Re-enter password", key="confirm_pwd")
    
    st.divider()
    col_a, col_b = st.columns(2)
    
    with col_a:
        if st.button("🔑 Reset Password", use_container_width=True, type="primary"):
            if not new_password:
                st.error("Please enter a new password")
            elif len(new_password) < 6:
                st.error("Password must be at least 6 characters")
            elif new_password != confirm_password:
                st.error("Passwords do not match")
            else:
                response, error = api_request('POST', f"/users/{user['id']}/reset-password", 
                                             data={'new_password': new_password})
                
                if error:
                    st.error(error)
                elif response and response.get('status') == 'success':
                    st.success(f"✅ Password reset successfully for {user.get('full_name', '')}!")
                    if 'reset_pwd_user' in st.session_state:
                        del st.session_state.reset_pwd_user
                    st.rerun()
                else:
                    st.error(response.get('error', 'Failed to reset password'))
    
    with col_b:
        if st.button("❌ Cancel", use_container_width=True):
            if 'reset_pwd_user' in st.session_state:
                del st.session_state.reset_pwd_user
            st.rerun()
