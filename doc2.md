``` mermaid
    %% ==========================================
    %% DIAGRAM 2: SCORECARD DATA FLOW
    %% ==========================================
    subgraph D2 ["Diagram 2 — Scorecard Data Flow"]
        direction TB
        
        subgraph D2_Save ["1. Save New Score"]
            direction TB
            D2_U1["User: Fill form + click Save All"] --> D2_J1["JS: POST action=golf_final_action_bulk_save"]
            D2_J1 --> D2_W1["WP: admin-ajax.php"] --> D2_P1["PHP: golf_final_action_bulk_save()"]
            D2_P1 --> D2_DB1[("DB: INSERT wp_golf_scores")]
            D2_DB1 --> D2_T1["TRG: AFTER INSERT"]
            D2_T1 --> D2_SP1A["CALL sp_update_low_hi_365()"]
            D2_T1 --> D2_SP1B["CALL sp_calculate_single_score_hcp()"]
            D2_SP1B --> D2_HH1[("HH: UPDATE wp_golf_handicap_history")]
            D2_HH1 --> D2_P1R["PHP: JSON success + row data"] --> D2_J1R["JS: New row appears in edit grid"]
        end

        subgraph D2_Update ["2. Update Existing Score"]
            direction TB
            D2_U2["User: Click SAVE on edit row"] --> D2_J2["JS: POST action=golf_final_action_update"]
            D2_J2 --> D2_W2["WP: admin-ajax.php"] --> D2_P2["PHP: golf_final_action_update()"]
            D2_P2 --> D2_DB2[("DB: UPDATE wp_golf_scores")]
            D2_DB2 --> D2_T2["TRG: AFTER UPDATE"]
            D2_T2 --> D2_SP2["CALL sp_repair_history_from_date()"]
            D2_SP2 --> D2_HH2[("HH: Rebuild history from date")]
            D2_HH2 --> D2_P2R["PHP: JSON success + net/diff/count"] --> D2_J2R["JS: Row updates in place"]
        end

        subgraph D2_Delete ["3. Delete Score"]
            direction TB
            D2_U3["User: Click DEL"] --> D2_J3["JS: POST action=golf_final_action_delete"]
            D2_J3 --> D2_W3["WP: admin-ajax.php"] --> D2_P3["PHP: golf_final_action_delete()"]
            D2_P3 --> D2_DB3[("DB: DELETE from wp_golf_scores")]
            D2_DB3 --> D2_T3["TRG: AFTER DELETE"]
            D2_T3 --> D2_SP3["CALL sp_repair_history_from_date()"]
            D2_SP3 --> D2_HH3[("HH: Rebuild history from date")]
            D2_HH3 --> D2_P3R["PHP: JSON success"] --> D2_J3R["JS: Row removed from grid"]
        end
    end
```