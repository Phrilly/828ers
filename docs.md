graph TD
    Site["828ers.im"]

    Site --> Home["🏠 Home Page"]
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

sequenceDiagram
    participant User
    participant JS as unified_javascript.js
    participant WP as WordPress admin-ajax.php
    participant PHP as Golf Master System.php
    participant DB as wp_golf_scores
    participant TRG as Triggers
    participant SP as sp_repair_history_from_date
    participant HH as wp_golf_handicap_history

    User->>JS: Fill form + click Save All
    JS->>WP: POST action=golf_final_action_bulk_save
    WP->>PHP: golf_final_action_bulk_save()
    PHP->>DB: INSERT into wp_golf_scores
    DB->>TRG: AFTER INSERT fires trg_scores_after_insert
    TRG->>SP: CALL sp_update_low_hi_365(score_id)
    TRG->>SP: CALL sp_calculate_single_score_hcp(score_id)
    SP->>HH: UPDATE wp_golf_handicap_history
    PHP-->>JS: JSON success + row data
    JS-->>User: New row appears in edit grid

    User->>JS: Click SAVE on edit row
    JS->>WP: POST action=golf_final_action_update
    WP->>PHP: golf_final_action_update()
    PHP->>DB: UPDATE wp_golf_scores
    DB->>TRG: AFTER UPDATE fires trg_scores_after_update
    TRG->>SP: CALL sp_repair_history_from_date(player_id, date)
    SP->>HH: Rebuild handicap history from date
    PHP-->>JS: JSON success + net/diff/count
    JS-->>User: Row updates in place

    User->>JS: Click DEL
    JS->>WP: POST action=golf_final_action_delete
    WP->>PHP: golf_final_action_delete()
    PHP->>DB: DELETE from wp_golf_scores
    DB->>TRG: AFTER DELETE fires trg_scores_after_delete
    TRG->>SP: CALL sp_repair_history_from_date(player_id, date)
    SP->>HH: Rebuild handicap history from date
    PHP-->>JS: JSON success
    JS-->>User: Row removed from grid

flowchart TD
    SCORE["wp_golf_scores\nscore_id, player_id, tee_id\ngross_score, pcc_adjustment\ndate_played, putts, gir"]

    SCORE -->|AFTER INSERT/UPDATE/DELETE| TRG["Triggers\ntrg_scores_after_insert\ntrg_scores_after_update\ntrg_scores_after_delete"]

    TRG -->|"1. sp_update_low_hi_365()"| LOWHI["Set low_hi_365\nLowest hcp_after in last 365 days"]
    TRG -->|"2. sp_repair_history_from_date()"| REPAIR

    subgraph REPAIR["sp_repair_history_from_date()"]
        direction TB
        R1["Calculate diff_raw\n= 113 × slope ÷ gross - rating - pcc"]
        R2["sp_apply_esr()\nESR -1.0 or -2.0 if diff 7-10 below HI"]
        R3["sp_calculate_single_score_hcp()\nBest 8 of last 20 differentials"]
        R4["Apply Soft Cap\n+3.0 above low_hi_365"]
        R5["Apply Hard Cap\n+5.0 above low_hi_365"]
        R6["UPDATE hcp_after, course_hcp\nplaying_hcp, net_score"]
        R1 --> R2 --> R3 --> R4 --> R5 --> R6
    end

    REPAIR --> HH["wp_golf_handicap_history\nhcp_before, hcp_after, low_hi_365\ndiff_raw, differential, esr_adj\ncap_type, cap_reduction\nis_best8, playing_hcp, net_score"]

    HH --> VDH["VIEW: wp_golf_dashboard_history\n(master view used by all shortcodes)"]

    VDH --> V1["view_handicap_index"]
    VDH --> V2["view_playing_handicaps"]
    VDH --> V3["view_golf_yearly_stats"]
    VDH --> V4["view_golf_rolling_averages"]
    VDH --> V5["view_golf_player_records"]
    VDH --> V6["view_golf_rounds_pivot"]

    V1 & V2 & V3 & V4 & V5 --> DASH["[golf_stats_dashboard]"]
    VDH --> HIST["[golf_round_history]"]
    VDH --> EDIT["[golf_edit_grid]"]
    V6 --> PIVOT["[golf_rounds_pivot]"]
    HH --> CHART["[golf_hcp_chart]"]

flowchart TD
    subgraph LIVE["✅ ACTIVE — Plugin Files (GitHub)"]
        P1["Golf Master System.php\ngolf_final_action_bulk_save\ngolf_final_action_delete\ngolf_final_action_update"]
        P2["Golf Round History.php\ngh_load_history AJAX"]
        P3["Golf Rounds Pivot.php\ngrp5_load AJAX"]
        P4["Handicap Index Chart.php\ngolf_hcp_chart shortcode"]
    end

    subgraph DEAD["⚠️ LEGACY — wp_snippets (should be deactivated)"]
        S1["Snippet #17: Ajax Action Handlers\ngolf_bulk_save_final\ngolf_delete_round_final\n⚠️ DIFFERENT action names"]
        S2["Snippet #18: delete receiver\ngolf_delete_round\n⚠️ YET ANOTHER action name"]
        S3["Snippet #12: Golf Round History\nDUPLICATE of Golf Round History.php"]
        S4["Snippet #27: Handicap Index Chart\nDUPLICATE of Handicap Index Chart.php"]
        S5["Snippet #23: Security Guard\ngolf_final_action_delete_secure\n⚠️ Calls non-existent functions"]
        S6["Snippet #7: Dashboard\nOLD dashboard shortcode"]
        S7["Snippet #5/#6: Form Submission + Update/Delete\nORIGINAL form-post versions\n⚠️ Conflict with AJAX versions"]
    end

    subgraph TRG["⚠️ DUPLICATE TRIGGERS on wp_golf_scores"]
        T1["trg_scores_after_insert\ntrg_scores_after_update\ntrg_scores_after_delete\n✅ CORRECT — calls sp_repair_history_from_date"]
        T2["trg_scores_insert\ntrg_scores_update\ntrg_scores_delete\n⚠️ OLDER — also calls sp_repair_history_from_date\nbut on 1-year lookback only"]
    end

    DEAD -.->|"may still fire if active"| P1
    T2 -.->|"fires alongside T1\ndouble-repair on every save"| T1
