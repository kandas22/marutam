"""Contractor Management Page"""
import streamlit as st
import pandas as pd


def show(api_request, user):
    """Display contractor management interface"""
    st.subheader("🏢 Contractor Management")
    
    is_admin = user.get('role') == 'admin'
    
    if is_admin:
        tab1, tab2 = st.tabs(["📋 All Contractors", "➕ Add Contractor"])
        
        with tab1:
            show_contractors_list(api_request, is_admin)
        
        with tab2:
            show_create_contractor_form(api_request)
    else:
        show_contractors_list(api_request, is_admin)


def show_contractors_list(api_request, is_admin):
    """Display list of contractors"""
    col1, col2 = st.columns([3, 1])
    
    with col1:
        search = st.text_input("🔍 Search", placeholder="Search contractors")
    
    with col2:
        st.write("")
        st.write("")
        refresh = st.button("🔄 Refresh")
    
    params = {'search': search} if search else {}
    response, error = api_request('GET', '/contractors', params=params)
    
    if error:
        st.error(error)
        return
    
    contractors = response.get('data', {}).get('contractors', []) if response else []
    
    if not contractors:
        st.info("No contractors found")
        return
    
    for contractor in contractors:
        with st.container():
            col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
            
            with col1:
                st.write(f"**{contractor.get('name', 'N/A')}**")
                st.caption(f"📧 {contractor.get('email', 'N/A')}")
            
            with col2:
                st.write(f"👤 {contractor.get('contact_person', 'N/A')}")
                st.caption(f"📞 {contractor.get('phone', 'N/A')}")
            
            with col3:
                st.write(f"GST: {contractor.get('gst_number', 'N/A')}")
                tender_year = contractor.get('tender_year', 'N/A')
                status = "🟢 Active" if contractor.get('is_active') else "🔴 Inactive"
                st.caption(f"{status} | Tender: {tender_year}")
            
            with col4:
                if is_admin:
                    col_a, col_b = st.columns(2)
                    with col_a:
                        if st.button("✏️", key=f"edit_c_{contractor['id']}", help="Edit"):
                            st.session_state.edit_contractor = contractor
                    with col_b:
                        if st.button("🗑️", key=f"del_c_{contractor['id']}", help="Deactivate"):
                            del_response, _ = api_request('DELETE', f"/contractors/{contractor['id']}")
                            st.rerun()
                
                if st.button("📦 Inventory", key=f"inv_{contractor['id']}", help="View Inventory"):
                    st.session_state.view_contractor_inv = contractor['id']
            
            st.divider()
    
    # View inventory dialog
    if 'view_contractor_inv' in st.session_state:
        show_contractor_inventory_dialog(api_request, st.session_state.view_contractor_inv)
    
    # Edit dialog
    if 'edit_contractor' in st.session_state:
        show_edit_contractor_dialog(api_request, st.session_state.edit_contractor)


def show_create_contractor_form(api_request):
    """Form to create new contractor"""
    with st.form("create_contractor_form"):
        st.markdown("### Add New Contractor")
        
        col1, col2 = st.columns(2)
        
        with col1:
            name = st.text_input("Contractor Name *", placeholder="Enter name")
            contact_person = st.text_input("Contact Person", placeholder="Enter contact person")
            phone = st.text_input("Phone", placeholder="Enter phone")
            tender_year = st.number_input("Tender Year", min_value=2020, max_value=2040, value=2026, step=1)
        
        with col2:
            email = st.text_input("Email", placeholder="Enter email")
            gst_number = st.text_input("GST Number", placeholder="Enter GST number")
            tender_start = st.date_input("Tender Start Date", key="tender_start")
            tender_end = st.date_input("Tender End Date", key="tender_end")
        
        address = st.text_area("Address", placeholder="Enter full address")
        notes = st.text_area("Notes", placeholder="Additional notes about this contractor")
        
        if st.form_submit_button("➕ Add Contractor", use_container_width=True):
            if not name:
                st.error("Contractor name is required")
            else:
                data = {
                    'name': name,
                    'contact_person': contact_person,
                    'phone': phone,
                    'email': email,
                    'gst_number': gst_number,
                    'address': address,
                    'tender_year': tender_year,
                    'tender_start_date': tender_start.strftime('%Y-%m-%d') if tender_start else None,
                    'tender_end_date': tender_end.strftime('%Y-%m-%d') if tender_end else None,
                    'notes': notes
                }
                
                response, error = api_request('POST', '/contractors', data=data)
                
                if error:
                    st.error(error)
                elif response and response.get('status') == 'success':
                    st.success("Contractor added successfully!")
                    st.balloons()
                else:
                    st.error(response.get('error', 'Failed to add contractor'))


@st.dialog("✏️ Edit Contractor", width="large")
def show_edit_contractor_dialog(api_request, contractor):
    """Dialog popup to edit contractor"""
    st.markdown(f"**Editing:** {contractor.get('name', '')}")
    st.divider()
    
    col1, col2 = st.columns(2)
    
    with col1:
        name = st.text_input("Name", value=contractor.get('name', ''))
        contact_person = st.text_input("Contact Person", value=contractor.get('contact_person', '') or '')
        phone = st.text_input("Phone", value=contractor.get('phone', '') or '')
    
    with col2:
        email = st.text_input("Email", value=contractor.get('email', '') or '')
        gst_number = st.text_input("GST Number", value=contractor.get('gst_number', '') or '')
        is_active = st.checkbox("Active", value=contractor.get('is_active', True))
    
    address = st.text_area("Address", value=contractor.get('address', '') or '')
    
    st.divider()
    col_a, col_b = st.columns(2)
    
    with col_a:
        if st.button("💾 Save", use_container_width=True, type="primary"):
            data = {
                'name': name,
                'contact_person': contact_person,
                'phone': phone,
                'email': email,
                'gst_number': gst_number,
                'address': address,
                'is_active': is_active
            }
            
            response, error = api_request('PUT', f"/contractors/{contractor['id']}", data=data)
            
            if response and response.get('status') == 'success':
                st.success("Updated!")
                if 'edit_contractor' in st.session_state:
                    del st.session_state.edit_contractor
                st.rerun()
            else:
                st.error(error or 'Failed')
    
    with col_b:
        if st.button("❌ Cancel", use_container_width=True):
            if 'edit_contractor' in st.session_state:
                del st.session_state.edit_contractor
            st.rerun()


@st.dialog("📦 Contractor Inventory", width="large")
def show_contractor_inventory_dialog(api_request, contractor_id):
    """Dialog popup to show inventory from a contractor"""
    response, error = api_request('GET', f'/contractors/{contractor_id}/inventory')
    
    if error:
        st.error(error)
        return
    
    inventory = response.get('data', {}).get('inventory', []) if response else []
    
    if not inventory:
        st.info("No inventory records")
    else:
        df = pd.DataFrame([{
            'Item': i.get('items', {}).get('name', 'N/A'),
            'Category': i.get('items', {}).get('category', 'N/A'),
            'Quantity': i.get('quantity', 0),
            'Unit': i.get('items', {}).get('unit', ''),
            'Received Date': i.get('received_date', 'N/A'),
            'Unit Price': i.get('unit_price', 'N/A')
        } for i in inventory])
        st.dataframe(df, use_container_width=True, hide_index=True)
    
    if st.button("Close", key="close_inv_dialog", use_container_width=True):
        if 'view_contractor_inv' in st.session_state:
            del st.session_state.view_contractor_inv
        st.rerun()
