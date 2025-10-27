import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
import plotly.graph_objects as go
import plotly.express as px
from typing import List, Dict, Tuple, Optional
import random
from datetime import datetime

# Page configuration
st.set_page_config(
    page_title="Container Stacking Optimizer",
    page_icon="📦",
    layout="wide"
)

# Initialize session state
if 'containers_df' not in st.session_state:
    st.session_state.containers_df = None
if 'layout_proposals' not in st.session_state:
    st.session_state.layout_proposals = []
if 'operation_type' not in st.session_state:
    st.session_state.operation_type = None
if 'area_configurations' not in st.session_state:
    st.session_state.area_configurations = {}
if 'selected_proposal' not in st.session_state:
    st.session_state.selected_proposal = None

class Container:
    def __init__(self, unit_number, iso_type, transporter, weight=None, port=None, category="Standard"):
        self.unit_number = unit_number
        self.iso_type = iso_type
        self.transporter = transporter
        self.weight = weight
        self.port = port
        self.category = category  # Standard, Reefer, Dangerous, Out-of-Gauge
        self.size = self._determine_size()
        self.weight_class = None  # Will be set based on weight
        self.priority = self._determine_priority()
    
    def _determine_size(self):
        """Determine if container is 6m or 12m based on ISO type"""
        if self.iso_type and '45' in self.iso_type:
            return 12
        elif self.iso_type and ('22' in self.iso_type or '20' in self.iso_type):
            return 6
        else:
            # Default based on common types
            return random.choice([6, 12])
    
    def _determine_priority(self):
        """Determine stacking priority"""
        if self.category == "Dangerous":
            return 1
        elif self.category == "Reefer":
            return 2
        elif self.category == "Out-of-Gauge":
            return 1
        else:
            return 3

class YardPosition:
    def __init__(self, area: str, row: int, column: str, max_tiers: int = 4):
        self.area = area
        self.row = row
        self.column = column
        self.max_tiers = max_tiers
        self.containers = []
        self.available_tiers = max_tiers
        self.container_length = self._get_container_length()
        self.is_reefer_position = self._check_reefer_position()
    
    def _get_container_length(self):
        """Determine container length based on row number"""
        if self.row % 4 == 0:  # Walkway
            return None
        elif self.row % 2 == 0:  # Even rows = 12m
            return 12
        else:  # Odd rows = 6m
            return 6
    
    def _check_reefer_position(self):
        """Check if this position is designated for reefers"""
        if self.area == "M2":
            return True  # Entire M2 is reefer area
        elif self.area == "Q1" and self.row in [2, 6, 10]:
            return True
        elif self.area == "Q2" and self.row in [2, 6, 10, 12]:
            return True
        return False
    
    def can_place_container(self, container: Container, area_weight_classes: List[int]) -> bool:
        """Check if container can be placed at this position"""
        if self.container_length != container.size:
            return False
        if self.available_tiers <= 0:
            return False
        if container.weight_class not in area_weight_classes:
            return False
        
        # Reefer containers must go in reefer positions
        if container.category == "Reefer" and not self.is_reefer_position:
            return False
            
        # Non-reefer containers should not block reefer positions if possible
        if container.category != "Reefer" and self.is_reefer_position:
            # Allow but with lower priority
            pass
            
        return True
    
    def place_container(self, container: Container) -> bool:
        """Place container at this position"""
        if self.available_tiers <= 0:
            return False
        
        self.containers.append(container)
        self.available_tiers -= 1
        return True
    
    def get_position_code(self) -> str:
        """Get position code like M226B3"""
        tier = len(self.containers) if self.containers else 1
        return f"{self.area}{self.row}{self.column}{tier}"

class YardArea:
    def __init__(self, name: str, allowed_weight_classes: List[int] = None, max_stack_height: int = 4):
        self.name = name
        self.allowed_weight_classes = allowed_weight_classes or [1, 2, 3, 4, 5, 6, 7, 8]
        self.max_stack_height = max_stack_height
        self.positions = self._initialize_positions()
    
    def _initialize_positions(self):
        """Initialize all positions for this area based on actual yard layout"""
        positions = []
        rows = list(range(1, 32))  # Rows 1-31
        columns = [chr(i) for i in range(65, 86)]  # Columns A-U (21 columns)
        
        for row in rows:
            for column in columns:
                if row % 4 == 0:  # Skip walkways (rows 4, 8, 12, 16, 20, 24, 28)
                    continue
                positions.append(YardPosition(self.name, row, column, self.max_stack_height))
        return positions
    
    def get_available_positions(self, container: Container) -> List[YardPosition]:
        """Get all available positions for this container"""
        available = []
        for position in self.positions:
            if position.can_place_container(container, self.allowed_weight_classes):
                available.append(position)
        return available
    
    def place_container(self, container: Container) -> Optional[str]:
        """Try to place container in this area, return position code if successful"""
        available_positions = self.get_available_positions(container)
        
        if available_positions:
            # Simple strategy: use first available position
            position = available_positions[0]
            if position.place_container(container):
                return position.get_position_code()
        
        return None

class YardLayoutOptimizer:
    def __init__(self):
        self.areas = {
            'M1': YardArea('M1'),
            'M2': YardArea('M2'), 
            'W1': YardArea('W1'),
            'W2': YardArea('W2'),
            'Q1': YardArea('Q1'),
            'Q2': YardArea('Q2')
        }
        
        self.weight_classes = {
            1: (0, 18.9), 2: (19, 23.4), 3: (23.5, 25.4),
            4: (25.5, 26.6), 5: (26.7, 28.4), 6: (28.5, 30),
            7: (30.1, 31), 8: (31.1, 50)
        }
        def detect_operation_type(self, df):
    """Auto-detect if it's Import or Export operation"""
    if 'Port' in df.columns and 'Weight' in df.columns:
        return 'EXPORT'
    elif 'Transporter' in df.columns:
        return 'IMPORT'
    return 'UNKNOWN'

def set_area_weight_classes(self, area_configurations: Dict):
    """Set weight classes for each area based on user input"""
    for area_name, weight_classes in area_configurations.items():
        if area_name in self.areas:
            self.areas[area_name].allowed_weight_classes = weight_classes

def assign_weight_classes(self, containers: List[Container]):
    """Assign weight classes to containers based on their weight"""
    for container in containers:
        if container.weight is not None:
            for class_id, (min_w, max_w) in self.weight_classes.items():
                if min_w <= container.weight <= max_w:
                    container.weight_class = class_id
                    break
            else:
                container.weight_class = 8  # Default to heaviest
        else:
            container.weight_class = random.randint(1, 8)

def optimize_import_layout(self, containers: List[Container], area_configurations: Dict) -> Dict:
    """Optimize IMPORT operations - group by transporter"""
    # Set area configurations
    self.set_area_weight_classes(area_configurations)
    self.assign_weight_classes(containers)
    
    placement_map = {}
    area_usage = {area_name: 0 for area_name in self.areas.keys()}
    
    # Group by transporter
    transporter_groups = {}
    for container in containers:
        if container.transporter not in transporter_groups:
            transporter_groups[container.transporter] = []
        transporter_groups[container.transporter].append(container)
    
    placed_count = 0
    
    # Strategy: Try to group each transporter in suitable areas
    for transporter, trans_containers in transporter_groups.items():
        # Find suitable areas for this transporter's containers
        suitable_areas = []
        for area_name, area in self.areas.items():
            # Check if area can accommodate all containers in this group
            can_accommodate = all(
                container.weight_class in area.allowed_weight_classes 
                for container in trans_containers
            )
            if can_accommodate:
                suitable_areas.append(area_name)
        
        # Try to place the entire group in one area
        group_placed = False
        for area_name in suitable_areas:
            area_placed_count = 0
            temp_placements = {}
            
            # Try to place all containers in this area
            for container in trans_containers:
                if container.unit_number not in placement_map:
                    position_code = self.areas[area_name].place_container(container)
                    if position_code:
                        temp_placements[container.unit_number] = {
                            'position': position_code,
                            'area': area_name,
                            'transporter': transporter,
                            'weight_class': container.weight_class,
                            'size': container.size,
                            'category': container.category
                        }
                        area_placed_count += 1
            
            # If we placed most of the group, accept the placements
            if area_placed_count >= len(trans_containers) * 0.8:  # 80% threshold
                placement_map.update(temp_placements)
                placed_count += area_placed_count
                area_usage[area_name] += area_placed_count
                group_placed = True
                break
        
        # If group placement failed, place individually
        if not group_placed:
            for container in trans_containers:
                if container.unit_number not in placement_map:
                    placed = self._place_container_anywhere(container, placement_map, area_usage)
                    if placed:
                        placed_count += 1
    
    return self._compile_result(containers, placement_map, area_usage, 'IMPORT')

def optimize_export_layout(self, containers: List[Container], area_configurations: Dict) -> Dict:
    """Optimize EXPORT operations - group by port and weight"""
    self.set_area_weight_classes(area_configurations)
    self.assign_weight_classes(containers)
    
    placement_map = {}
    area_usage = {area_name: 0 for area_name in self.areas.keys()}
    
    # Group by port and weight class
    port_groups = {}
    for container in containers:
        if container.port not in port_groups:
            port_groups[container.port] = {}
        if container.weight_class not in port_groups[container.port]:
            port_groups[container.port][container.weight_class] = []
        port_groups[container.port][container.weight_class].append(container)
    
    placed_count = 0
    
    # Place by port groups within appropriate weight class areas
    for port, weight_groups in port_groups.items():
        for weight_class, class_containers in weight_groups.items():
            # Find areas that allow this weight class
            suitable_areas = [
                area_name for area_name, area in self.areas.items() 
                if weight_class in area.allowed_weight_classes
            ]
            
            # Try to place in suitable areas
            for area_name in suitable_areas:
                if not class_containers:
                    break
                
                # Place as many as possible in this area
                temp_placed = 0
                for container in class_containers[:]:  # Copy for safe removal
                    if container.unit_number not in placement_map:
                        position_code = self.areas[area_name].place_container(container)
                        if position_code:
                            placement_map[container.unit_number] = {
                                'position': position_code,
                                'area': area_name,
                                'port': port,
                                'weight_class': weight_class,
                                'size': container.size,
                                'category': container.category
                            }
                            placed_count += 1
                            area_usage[area_name] += 1
                            temp_placed += 1
                            class_containers.remove(container)
    
    # Place any remaining containers
    remaining_containers = [c for c in containers if c.unit_number not in placement_map]
    for container in remaining_containers:
        placed = self._place_container_anywhere(container, placement_map, area_usage)
        if placed:
            placed_count += 1
    
    return self._compile_result(containers, placement_map, area_usage, 'EXPORT')

def _place_container_anywhere(self, container: Container, placement_map: Dict, area_usage: Dict) -> bool:
    """Try to place container in any available area"""
    for area_name, area in self.areas.items():
        if container.weight_class in area.allowed_weight_classes:
            position_code = area.place_container(container)
            if position_code:
                placement_map[container.unit_number] = {
                    'position': position_code,
                    'area': area_name,
                    'transporter': container.transporter,
                    'port': container.port,
                    'weight_class': container.weight_class,
                    'size': container.size,
                    'category': container.category
                }
                area_usage[area_name] += 1
                return True
    return False

def _compile_result(self, containers: List[Container], placement_map: Dict, 
                   area_usage: Dict, operation_type: str) -> Dict:
    """Compile optimization results"""
    total_containers = len(containers)
    placed_count = len(placement_map)
    
    # Calculate space utilization
    total_positions = sum(len(area.positions) for area in self.areas.values())
    used_positions = sum(usage for usage in area_usage.values())
    space_utilization = (used_positions / total_positions) * 100 if total_positions > 0 else 0
    
    # Calculate grouping efficiency
    grouping_efficiency = self._calculate_grouping_efficiency(placement_map, operation_type)
    
    # Area details
    area_details = {}
    for area_name, usage in area_usage.items():
        if usage > 0:
            total_area_positions = len(self.areas[area_name].positions)
            utilization = (usage / total_area_positions) * 100
            area_details[area_name] = {
                'containers_placed': usage,
                'utilization': f"{utilization:.1f}%",
                'weight_classes': self.areas[area_name].allowed_weight_classes
            }
    
    return {
        'placement_map': placement_map,
        'efficiency': (placed_count / total_containers) * 100,
        'space_utilization': f"{space_utilization:.1f}%",
        'grouping_efficiency': f"{grouping_efficiency:.1f}%",
        'area_usage': area_details,
        'total_placed': placed_count,
        'total_containers': total_containers,
        'details': f"{operation_type} optimization completed",
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

def _calculate_grouping_efficiency(self, placement_map: Dict, operation_type: str) -> float:
    """Calculate how well containers are grouped"""
    if not placement_map:
        return 0
    
    placements = list(placement_map.values())
    grouped_pairs = 0
    total_pairs = len(placements) - 1
    
    for i in range(len(placements) - 1):
        current = placements[i]
        next_place = placements[i + 1]
        
        if operation_type == 'IMPORT':
            if (current['transporter'] == next_place['transporter'] and 
                current['area'] == next_place['area']):
                grouped_pairs += 1
        else:  # EXPORT
            if (current['port'] == next_place['port'] and 
                current['area'] == next_place['area'] and
                abs(current['weight_class'] - next_place['weight_class']) <= 1):
                grouped_pairs += 1
    
    return (grouped_pairs / total_pairs) * 100 if total_pairs > 0 else 0

def generate_multiple_proposals(self, containers: List[Container], 
                              operation_type: str, area_configurations: Dict,
                              num_proposals: int = 3) -> List[Dict]:
    """Generate multiple layout proposals"""
    proposals = []
    
    for i in range(num_proposals):
        # Reset all areas for new proposal
        self.areas = {
            'M1': YardArea('M1'),
            'M2': YardArea('M2'), 
            'W1': YardArea('W1'),
            'W2': YardArea('W2'),
            'Q1': YardArea('Q1'),
            'Q2': YardArea('Q2')
        }
        
        if operation_type == 'IMPORT':
            result = self.optimize_import_layout(containers, area_configurations)
        else:
            result = self.optimize_export_layout(containers, area_configurations)
        
        proposals.append({
            'id': i + 1,
            'score': round(result['efficiency']),
            'space_utilization': result['space_utilization'],
            'grouping_efficiency': result['grouping_efficiency'],
            'details': result['details'],
            'placement_map': result['placement_map'],
            'area_usage': result['area_usage'],
            'containers_placed': result['total_placed'],
            'total_containers': result['total_containers'],
            'timestamp': result['timestamp'],
            'strategy': f"Proposal {i+1}"
        })
    
    return proposals
    def main():
    st.title("📦 Container Stacking Optimizer")
    st.markdown("---")
    
    # Initialize optimizer
    optimizer = YardLayoutOptimizer()
    
    # Sidebar for configuration
    with st.sidebar:
        st.header("Configuration")
        
        # Operation type selection
        operation_type = st.radio(
            "Operation Type",
            ["Auto-detect", "IMPORT", "EXPORT"],
            help="Auto-detect will determine from uploaded data"
        )
        
        # File upload
        uploaded_file = st.file_uploader("Upload Container Data", type=['xlsx', 'csv'])
        
        if uploaded_file:
            if uploaded_file.name.endswith('.xlsx'):
                df = pd.read_excel(uploaded_file)
            else:
                df = pd.read_csv(uploaded_file)
            
            st.session_state.containers_df = df
            
            # Determine operation type
            if operation_type == "Auto-detect":
                st.session_state.operation_type = optimizer.detect_operation_type(df)
            else:
                st.session_state.operation_type = operation_type
            
            st.success(f"Data loaded! Operation: {st.session_state.operation_type}")
            
            # Display data preview
            st.subheader("Data Preview")
            st.dataframe(df.head(5))
    
    # Main content area
    col1, col2 = st.columns([2, 1])
    
    with col1:
        if st.session_state.containers_df is not None:
            st.header("Area Configuration")
            
            # Area weight class configuration
            st.subheader("Set Weight Classes for Each Area")
            area_configurations = {}
            
            cols = st.columns(3)
            areas = ['M1', 'M2', 'W1', 'W2', 'Q1', 'Q2']
            
            for i, area in enumerate(areas):
                with cols[i % 3]:
                    st.write(f"**{area}**")
                    weight_classes = st.multiselect(
                        f"Select weight classes for {area}",
                        options=[1, 2, 3, 4, 5, 6, 7, 8],
                        default=[1, 2, 3, 4, 5, 6, 7, 8],
                        key=f"weight_{area}"
                    )
                    area_configurations[area] = weight_classes
            
            st.session_state.area_configurations = area_configurations
            
            # Optimization controls
            st.header("Layout Optimization")
            col1_1, col1_2 = st.columns(2)
            with col1_1:
                num_proposals = st.slider("Number of layout proposals", 1, 5, 3)
            with col1_2:
                optimize_button = st.button("🚀 Generate Layout Proposals", type="primary", use_container_width=True)
            
            if optimize_button:
                with st.spinner("Generating optimized layouts..."):
                    # Convert DataFrame to Container objects
                    containers = []
                    for _, row in st.session_state.containers_df.iterrows():
                        container = Container(
                            unit_number=row.get('Unit Number', f"CONT{random.randint(10000, 99999)}"),
                            iso_type=row.get('ISO Type', '22G1'),
                            transporter=row.get('Transporter Name', 'Unknown'),
                            weight=row.get('Weight', random.uniform(10, 35)),
                            port=row.get('Port', 'DUBAI'),
                            category=row.get('Category', 'Standard')
                        )
                        containers.append(container)
                    
                    proposals = optimizer.generate_multiple_proposals(
                        containers, 
                        st.session_state.operation_type,
                        st.session_state.area_configurations,
                        num_proposals
                    )
                    st.session_state.layout_proposals = proposals
                
                st.success(f"Generated {len(proposals)} layout proposals!")
            
            # Display proposals
            if st.session_state.layout_proposals:
                st.subheader("Layout Proposals")
                
                for i, proposal in enumerate(st.session_state.layout_proposals):
                    with st.expander(
                        f"Proposal {i+1} - {proposal['score']}% Efficiency", 
                        expanded=i==0
                    ):
                        display_proposal(proposal, i)
        
        else:
            display_welcome_screen()
    
    with col2:
        st.header("Quick Actions")
        
        if st.session_state.layout_proposals:
            # Export options
            selected_proposal = st.session_state.layout_proposals[0]
            
            st.download_button(
                label="📊 Export to Excel",
                data=generate_excel_export(selected_proposal),
                file_name=f"container_assignments_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.ms-excel",
                use_container_width=True
            )
            
            st.download_button(
                label="🖨️ Printable Summary",
                data=generate_printable_summary(selected_proposal),
                file_name=f"yard_plan_summary_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                mime="text/plain",
                use_container_width=True
            )
            
            # Yard overview
            st.subheader("Yard Overview")
            display_yard_overview()

def display_proposal(proposal, proposal_id):
    """Display a layout proposal"""
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Efficiency Score", f"{proposal['score']}%")
    with col2:
        st.metric("Containers Placed", f"{proposal['containers_placed']}/{proposal['total_containers']}")
    with col3:
        st.metric("Space Utilization", proposal['space_utilization'])
    
    st.write(f"**Grouping Efficiency:** {proposal['grouping_efficiency']}")
    st.write(f"**Generated:** {proposal['timestamp']}")
    
    # Area usage breakdown
    st.subheader("Area Utilization")
    if proposal['area_usage']:
        area_data = []
        for area_name, usage in proposal['area_usage'].items():
            area_data.append({
                'Area': area_name,
                'Containers': usage['containers_placed'],
                'Utilization': usage['utilization'],
                'Weight Classes': str(usage['weight_classes'])
            })
        
        area_df = pd.DataFrame(area_data)
        st.dataframe(area_df, use_container_width=True)
    else:
        st.warning("No containers were placed in any area")
    
    # Container assignments
    st.subheader("Container Assignments")
    if proposal['placement_map']:
        placement_df = pd.DataFrame.from_dict(proposal['placement_map'], orient='index')
        st.dataframe(placement_df.head(10))
        
        if len(placement_df) > 10:
            st.write(f"... and {len(placement_df) - 10} more containers")
    else:
        st.error("No containers were placed in this proposal")
    
    # Action buttons
    col1, col2 = st.columns(2)
    with col1:
        if st.button(f"✅ Select Proposal {proposal_id + 1}", key=f"select_{proposal_id}", use_container_width=True):
            st.session_state.selected_proposal = proposal
            st.success(f"Proposal {proposal_id + 1} selected for implementation!")
    with col2:
        if st.button(f"📋 View Details {proposal_id + 1}", key=f"details_{proposal_id}", use_container_width=True):
            st.info(f"Detailed view for Proposal {proposal_id + 1}")

def display_yard_overview():
    """Display yard overview information"""
    st.info("""
    **Yard Layout:**
    - **Areas:** M1, M2, W1, W2, Q1, Q2
    - **Rows:** 1-31 (walkways at 4,8,12,16,20,24,28)
    - **Columns:** A-U (21 columns)
    - **6m containers:** Odd rows (1,3,5,7,9,11,13,15,17,19,21,23,25,27,29,31)
    - **12m containers:** Even rows (2,6,10,14,18,22,26,30)
    
    **Reefer Positions:**
    - M2: All positions
    - Q1: Rows 2, 6, 10
    - Q2: Rows 2, 6, 10, 12
    """)

def display_welcome_screen():
    """Display welcome screen with instructions"""
    st.info("📤 Please upload your container data to begin optimization")
    
    # Sample data formats
    st.subheader("Expected Excel Formats:")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**IMPORT Format:**")
        st.code("""
Unit Number | ISO Type | Transporter Name | Category
----------- | -------- | ---------------- | --------
CONT12345   | 45G1     | Transporter A    | Standard
CONT67890   | 22G1     | Transporter B    | Reefer
        """)
    
    with col2:
        st.write("**EXPORT Format:**")
        st.code("""
Unit Number | ISO Type | Weight | Port     | Category
----------- | -------- | ------ | -------- | --------
CONT12345   | 45G1     | 22.5   | JEBEL ALI| Standard
CONT67890   | 22G1     | 18.2   | DUBAI    | Reefer
        """)

def generate_excel_export(proposal):
    """Generate Excel export"""
    output = BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Container assignments sheet
        if proposal['placement_map']:
            assignments_df = pd.DataFrame.from_dict(proposal['placement_map'], orient='index')
            assignments_df.reset_index(inplace=True)
            assignments_df.rename(columns={'index': 'Unit Number'}, inplace=True)
            assignments_df.to_excel(writer, sheet_name='Container_Assignments', index=False)
        else:
            pd.DataFrame().to_excel(writer, sheet_name='Container_Assignments')
        
        # Summary sheet
        summary_data = {
            'Metric': [
                'Proposal ID', 'Efficiency Score', 'Containers Placed', 
                'Total Containers', 'Space Utilization', 'Grouping Efficiency',
                'Timestamp'
            ],
            'Value': [
                proposal['id'], f"{proposal['score']}%", 
                proposal['containers_placed'], proposal['total_containers'],
                proposal['space_utilization'], proposal['grouping_efficiency'],
                proposal['timestamp']
            ]
        }
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
        
        # Area usage sheet
        if proposal['area_usage']:
            area_data = []
            for area_name, usage in proposal['area_usage'].items():
                area_data.append({
                    'Area': area_name,
                    'Containers Placed': usage['containers_placed'],
                    'Utilization Rate': usage['utilization'],
                    'Allowed Weight Classes': str(usage['weight_classes'])
                })
            area_df = pd.DataFrame(area_data)
            area_df.to_excel(writer, sheet_name='Area_Utilization', index=False)
    
    return output.getvalue()

def generate_printable_summary(proposal):
    """Generate printable text summary"""
    summary = f"""
CONTAINER STACKING OPTIMIZATION REPORT
Generated: {proposal['timestamp']}
Proposal: {proposal['id']}

SUMMARY:
--------
Efficiency Score: {proposal['score']}%
Containers Placed: {proposal['containers_placed']} / {proposal['total_containers']}
Space Utilization: {proposal['space_utilization']}
Grouping Efficiency: {proposal['grouping_efficiency']}

AREA UTILIZATION:
----------------
"""
    
    if proposal['area_usage']:
        for area_name, usage in proposal['area_usage'].items():
            summary += f"{area_name}: {usage['containers_placed']} containers ({usage['utilization']})\n"
    else:
        summary += "No containers placed in any area\n"
    
    summary += f"\nDetails: {proposal['details']}"
    
    return summary.encode('utf-8')

if __name__ == "__main__":
    main()