from nicegui import ui

def apply_styles():
    ui.colors(primary='#2D667E', secondary='#E9D060', accent='#E9D060')
    # Removing fixed body centering to allow full dynamic width
    ui.query('body').style(
        'background-color: #F4F4F4; margin: 0; font-family: "Roboto", sans-serif;'
    )

def nav_card(title, icon, route, subtitle=None):
    """Tile that expands dynamically and removes the 'dot' colons."""
    # 'w-full' makes the tile expand to whatever container it is in
    with ui.card().classes('w-full q-pa-md cursor-pointer hover:bg-grey-1 shadow-sm overflow-hidden') \
            .on('click', lambda: ui.navigate.to(route)):
        
        with ui.row().classes('w-full items-center no-wrap'):
            # FIXED: Removed the 'm:' prefix which was causing the ': icon_name' text/dots
            ui.icon(icon, color='primary').classes('text-4xl shrink-0')
            
            # 'grow' makes this column take up all remaining horizontal space
            with ui.column().classes('grow q-ml-md overflow-hidden'):
                # Dynamic text sizing using tailwind 'text-base' to 'text-lg'
                ui.label(title).classes('font-bold text-lg text-dark leading-tight')
                
                if subtitle:
                    ui.label(subtitle).classes('text-sm text-grey-6 leading-tight mt-1')