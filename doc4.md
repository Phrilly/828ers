``` mermaid
%% ==========================================
    %% DIAGRAM 4: KNOWN DUPLICATES AND CONFLICTS
    %% ==========================================
    subgraph D4 ["Diagram 4 — Known Duplicates and Conflicts"]
        direction TB
        
        subgraph D4_LIVE ["ACTIVE — Plugin Files on GitHub"]
            direction TB
            D4_P1["Golf Master System.php\ngolf_final_action_bulk_save\ngolf_final_action_delete\ngolf_final_action_update"]
            D4_P2["Golf Round History.php\ngh_load_history AJAX"]
            D4_P3["Golf Rounds Pivot.php\ngrp5_load AJAX"]
            D4_P4["Handicap Index Chart.php\ngolf_hcp_chart shortcode"]
        end

        subgraph D4_DEAD ["LEGACY — wp_snippets table, should be deactivated"]
            direction TB
            D4_S1["Snippet 17: Ajax Action Handlers\ngolf_bulk_save_final\ngolf_delete_round_final\nDIFFERENT action names"]
            D4_S2["Snippet 18: delete receiver\ngolf_delete_round\nYET ANOTHER action name"]
            D4_S3["Snippet 12: Golf Round History\nDUPLICATE of Golf Round History.php"]
            D4_S4["Snippet 27: Handicap Index Chart\nDUPLICATE of Handicap Index Chart.php"]
            D4_S5["Snippet 23: Security Guard\ngolf_final_action_delete_secure\nCalls non-existent functions"]
            D4_S6["Snippet 7: Dashboard\nOLD dashboard shortcode"]
            D4_S7["Snippet 5 and 6: Form Submission\nORIGINAL form-post versions\nConflict with AJAX versions"]
        end

        subgraph D4_TRIGS ["DUPLICATE TRIGGERS on wp_golf_scores"]
            direction TB
            D4_T1["trg_scores_after_insert\ntrg_scores_after_update\ntrg_scores_after_delete\nCORRECT - calls sp_repair_history_from_date"]
            D4_T2["trg_scores_insert\ntrg_scores_update\ntrg_scores_delete\nOLDER - also calls sp_repair_history_from_date\ndouble-repair on every save"]
        end

        D4_S1 -.->|"may still fire if active"| D4_P1
        D4_T2 -.->|"fires alongside T1"| D4_T1
    end
```