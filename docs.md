flowchart TD

    %% ==========================================
    %% DIAGRAM 1: SITE OVERVIEW
    %% ==========================================
    subgraph D1 ["Diagram 1 — Site Overview"]
        direction TB
        Site["828ers.im"] --> Home["🏠 Home Page"]
        Site --> Scorecard["📋 Scorecard Page"]
        Site --> Rounds["📊 Rounds Page"]
        
        Home --> SC1["[golf_stats_dashboard]"]
        Home --> SC2["[golf_round_history]"]
        Home --> SC3["[golf_hcp_chart]"]
        Home --> SC4["[golf_rounds_pivot]"]
        
        Scorecard --> SC5["[golf_scorecard_entry]"]
        Scorecard --> SC6["[golf_edit_grid]"]
        
        SC1 --> F1["Golf Stats Dashboard.php"]
        SC2 --> F2["Golf Round History.php"]
        SC3 --> F3["Handicap Index Chart.php"]
        SC4 --> F4["Golf Rounds Pivot.php"]
        SC5 --> F5["Golf Master System.php"]
        SC6 --> F5
    end

    %% ==========================================
    %% DIAGRAM 2: SCORECARD DATA FLOW (Converted to Flow)
    %% ==========================================
    subgraph D2 ["Diagram 2 — Scorecard Data Flow"]
        direction TB
        
        subgraph Flow_Save ["1. Save New Score"]
            direction TB
            U1["User: Fill form + click Save All"] --> J1["JS: POST action=golf_final_action_bulk_save"]
            J1 --> W1["WP: admin-ajax.php"] --> P1["PHP: golf_final_action_bulk_save()"]
            P1 --> DB1[("DB: INSERT into wp_golf_scores")]
            DB1 --> T1["TRG: AFTER INSERT (trg_scores_after_insert)"]
            T1 --> SP1A["SP: CALL sp_update_low_hi_365()"]
            T1 --> SP1B["SP: CALL sp_calculate_single_score_hcp()"]
            SP1B --> HH1[("HH: UPDATE wp_golf_handicap_history")]
            HH1 --> P1R["PHP: JSON success + row data"] --> J1R["JS: New row appears in edit grid"]
        end

        subgraph Flow_Update ["2. Update Existing Score"]
            direction TB
            U2["User: Click SAVE on edit row"] --> J2["JS: POST action=golf_final_action_update"]
            J2 --> W2["WP: admin-ajax.php"] --> P2["PHP: golf_final_action_update()"]
            P2 --> DB2[("DB: UPDATE wp_golf_scores")]
            DB2 --> T2["TRG: AFTER UPDATE (trg_scores_after_update)"]
            T2 --> SP2["SP: CALL sp_repair_history_from_date()"]
            SP2 --> HH2[("HH: Rebuild handicap history from date")]
            HH2 --> P2R["PHP: JSON success + net/diff/count"] --> J2R["JS: Row updates in place"]
        end

        subgraph Flow_Delete ["3. Delete Score"]
            direction TB
            U3["User: Click DEL"] --> J3["JS: POST action=golf_final_action_delete"]
            J3 --> W3["WP: admin-ajax.php"] --> P3["PHP: golf_final_action_delete()"]
            P3 --> DB3[("DB: DELETE from wp_golf_scores")]
            DB3 --> T3["TRG: AFTER DELETE (trg_scores_after_delete)"]
            T3 --> SP3["SP: CALL sp_repair_history_from_date()"]
            SP3 --> HH3[("HH: Rebuild handicap history from date")]
            HH3 --> P3R["PHP: JSON success"] --> J3R["JS: Row removed from grid"]
        end
    end

    %% ==========================================
    %% DIAGRAM 3: HANDICAP CALCULATION CHAIN
    %% ==========================================
    subgraph D3 ["Diagram 3 — Handicap Calculation Chain"]
        direction TB
        SCORE["wp_golf_scores\nscore_id, player_id, tee_id\ngross_score, pcc_adjustment\ndate_played, putts, gir"] 
        SCORE -->|AFTER INSERT/UPDATE/DELETE| TRG_D3["Triggers\ntrg_scores_after_insert\ntrg_scores_after_update\ntrg_scores_after_delete"]
        
        TRG_D3 -->|"1. sp_update_low_hi_365()"| LOWHI["Set low_hi_365\nLowest hcp_after in last 365 days"]
        TRG_D3 -->|"2. sp_repair_history_from_date()"| R1
        
        subgraph REPAIR ["sp_repair_history_from_date()"]
            direction TB
            R1["Calculate diff_raw\n= 113 x slope / gross - rating - pcc"] --> R2["sp_apply_esr()\nESR -1.0 or -2.0 if diff 7-10 below HI"]
            R2 --> R3["sp_calculate_single_score_hcp()\nBest 8 of last 20 differentials"]
            R3 --> R4["Apply Soft Cap\n+3.0 above low_hi_365"]
            R4 --> R5["Apply Hard Cap\n+5.0 above low_hi_365"]
            R5 --> R6["UPDATE hcp_after, course_hcp\nplaying_hcp, net_score"]
        end
        
        R6 --> HH_D3["wp_golf_handicap_history\nhcp_before, hcp_after, low_hi_365\ndiff_raw, differential, esr_adj\ncap_type, cap_reduction\nis_best8, playing_hcp, net_score"]
        
        HH_D3 --> VDH["VIEW: wp_golf_dashboard_history\nmaster view used by all shortcodes"]
        VDH --> V1["view_handicap_index"]
        VDH --> V2["view_playing_handicaps"]
        VDH --> V3["view_golf_yearly_stats"]
        VDH --> V4["view_golf_rolling_averages"]
        VDH --> V5["view_golf_player_records"]
        VDH --> V6["view_golf_rounds_pivot"]
        
        V1 & V2 & V3 & V4 & V5 --> DASH_D3["[golf_stats_dashboard]"]
        VDH --> HIST_D3["[golf_round_history]"]
        VDH --> EDIT_D3["[golf_edit_grid]"]
        V6 --> PIVOT_D3["[golf_rounds_pivot]"]
        HH_D3 --> CHART_D3["[golf_hcp_chart]"]
    end

    %% ==========================================
    %% DIAGRAM 4: KNOWN DUPLICATES AND CONFLICTS
    %% ==========================================
    subgraph D4 ["Diagram 4 — Known Duplicates and Conflicts"]
        direction TB
        
        subgraph LIVE ["ACTIVE — Plugin Files on GitHub"]
            direction TB
            P1_D4["Golf Master System.php\ngolf_final_action_bulk_save\ngolf_final_action_delete\ngolf_final_action_update"]
            P2_D4["Golf Round History.php\ngh_load_history AJAX"]
            P3_D4["Golf Rounds Pivot.php\ngrp5_load AJAX"]
            P4_D4["Handicap Index Chart.php\ngolf_hcp_chart shortcode"]
        end

        subgraph DEAD ["LEGACY — wp_snippets table, should be deactivated"]
            direction TB
            S1["Snippet 17: Ajax Action Handlers\ngolf_bulk_save_final\ngolf_delete_round_final\nDIFFERENT action names"]
            S2["Snippet 18: delete receiver\ngolf_delete_round\nYET ANOTHER action name"]
            S3["Snippet 12: Golf Round History\nDUPLICATE of Golf Round History.php"]
            S4["Snippet 27: Handicap Index Chart\nDUPLICATE of Handicap Index Chart.php"]
            S5["Snippet 23: Security Guard\ngolf_final_action_delete_secure\nCalls non-existent functions"]
            S6["Snippet 7: Dashboard\nOLD dashboard shortcode"]
            S7["Snippet 5 and 6: Form Submission\nORIGINAL form-post versions\nConflict with AJAX versions"]
        end

        subgraph TRIGS ["DUPLICATE TRIGGERS on wp_golf_scores"]
            direction TB
            T1_D4["trg_scores_after_insert\ntrg_scores_after_update\ntrg_scores_after_delete\nCORRECT - calls sp_repair_history_from_date"]
            T2_D4["trg_scores_insert\ntrg_scores_update\ntrg_scores_delete\nOLDER - also calls sp_repair_history_from_date\ndouble-repair on every save"]
        end

        S1 -.->|"may still fire if active"| P1_D4
        T2_D4 -.->|"fires alongside T1"| T1_D4
    end