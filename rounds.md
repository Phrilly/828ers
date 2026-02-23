```mermaid
flowchart TD
    Start((User Action)) --> Visit[Visit 'Rounds' Page \nor Click Pagination Link]
    
    subgraph Frontend ["Frontend (JavaScript in shortcode)"]
        direction TB
        Visit --> JS_Load[Call loadPage(page)]
        JS_Load --> JS_Loading[Add 'is-loading' class \nto #grp5-tablewrap]
        JS_Loading --> JS_Fetch[Fetch API POST to admin-ajax.php\n(action: 'grp5_load', nonce, page)]
    end

    subgraph Backend ["Backend (Golf Rounds Pivot.php)"]
        direction TB
        JS_Fetch --> PHP_Init[grp5_load() executes]
        PHP_Init --> PHP_Nonce{Verify Nonce}
        PHP_Nonce -- Valid --> DB_Schema[(1. Query INFORMATION_SCHEMA\nDiscover dynamic player columns\np1_name, p2_name, etc.)]
        DB_Schema --> DB_Count[(2. Query COUNT(*)\nin view_golf_rounds_pivot)]
        DB_Count --> DB_Rows[(3. Query page rows\nwith LIMIT & OFFSET)]
        
        DB_Rows --> PHP_BuildTable[Build HTML Table:\nIterate rows and dynamically output\nGross/Hcp/Nett + Winner for each player]
        PHP_BuildTable --> PHP_BuildPager[Build HTML Pagination String]
        PHP_BuildPager --> PHP_JSON[Return JSON:\n{ success: true, data: { table, pagination, range } }]
    end

    subgraph DOM_Update ["DOM Update (Frontend)"]
        direction TB
        PHP_JSON --> JS_Receive[JS receives & parses JSON]
        JS_Receive --> DOM_Inject[Inject HTML into DOM:\n#grp5-tablewrap\n#grp5-pager\n#grp5-range]
        DOM_Inject --> JS_Done[Remove 'is-loading' class]
        JS_Done --> JS_Scroll[Smooth scroll to #grp5-app]
    end
    
    PHP_Nonce -- Invalid / Error --> JS_Error[Show 'Error loading rounds']
    
    JS_Scroll --> End((Ready for Next Action))
    JS_Error --> End
    
    %% Styling
    style Start fill:#f9f,stroke:#333,stroke-width:2px
    style End fill:#69f,stroke:#333,stroke-width:2px
    style Frontend fill:#e1f5fe,stroke:#01579b
    style Backend fill:#e8f5e9,stroke:#1b5e20
    style DOM_Update fill:#fff3e0,stroke:#e65100
    style PHP_Nonce fill:#ffe0b2,stroke:#e65100
```