-- Auto-generated demo schema (do not edit manually)
-- Generated from axion.db table definitions
-- Update this file when the production schema changes by re-running:
--   python3 scripts/export_demo_schema.py

CREATE TABLE agent_aliases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        alias TEXT NOT NULL UNIQUE COLLATE NOCASE,
        canonical_name TEXT NOT NULL,
        user_id INTEGER,
        active INTEGER NOT NULL DEFAULT 1,
        ambiguous INTEGER NOT NULL DEFAULT 0,
        notes TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );

CREATE TABLE agent_locations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL UNIQUE,
        lat REAL NOT NULL,
        lng REAL NOT NULL,
        accuracy REAL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );

CREATE TABLE ai_usage_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        job_id INTEGER,
        feature TEXT NOT NULL,
        model TEXT,
        tokens_used INTEGER,
        key_source TEXT NOT NULL DEFAULT 'replit',
        created_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(job_id) REFERENCES jobs(id)
    );

CREATE TABLE auction_yards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            address TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        , contact_name TEXT, mobile TEXT, other_phone TEXT, email TEXT, suburb TEXT, state TEXT, postcode TEXT, notes TEXT, created_by_user_id INTEGER, phone TEXT);

CREATE TABLE audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        actor_user_id INTEGER,
        entity_type TEXT NOT NULL,
        entity_id INTEGER,
        action TEXT NOT NULL,
        message TEXT NOT NULL,
        meta_json TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(actor_user_id) REFERENCES users(id)
    );

CREATE TABLE booking_types (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        active INTEGER NOT NULL DEFAULT 1
    );

CREATE TABLE client_update_requests (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id              INTEGER NOT NULL,
        sent_by_user_id     INTEGER,
        sent_at             TEXT NOT NULL,
        recipient_email     TEXT,
        subject             TEXT,
        body_snapshot       TEXT,
        reply_to            TEXT NOT NULL DEFAULT 'office@swpirecoveries.com',
        result_status       TEXT NOT NULL DEFAULT 'sent',
        related_note_id     INTEGER,
        FOREIGN KEY(job_id)          REFERENCES jobs(id),
        FOREIGN KEY(sent_by_user_id) REFERENCES users(id)
    );

CREATE TABLE clients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT,
        email TEXT,
        address TEXT,
        notes TEXT,
        created_at TEXT NOT NULL
    , updated_at TEXT NOT NULL DEFAULT '', nickname TEXT);

CREATE TABLE contact_emails (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_type TEXT NOT NULL,
        entity_id INTEGER NOT NULL,
        label TEXT,
        email TEXT NOT NULL,
        created_at TEXT NOT NULL
    );

CREATE TABLE contact_phone_numbers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_type TEXT NOT NULL,
        entity_id INTEGER NOT NULL,
        label TEXT NOT NULL,
        phone_number TEXT NOT NULL,
        created_at TEXT NOT NULL
    );

CREATE TABLE conversation_participants (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            user_id         INTEGER NOT NULL,
            joined_at       TEXT    NOT NULL,
            UNIQUE(conversation_id, user_id),
            FOREIGN KEY(conversation_id) REFERENCES conversations(id),
            FOREIGN KEY(user_id)         REFERENCES users(id)
        );

CREATE TABLE conversations (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            type       TEXT    NOT NULL DEFAULT 'direct',
            job_id     INTEGER,
            subject    TEXT,
            created_at TEXT    NOT NULL,
            updated_at TEXT    NOT NULL,
            FOREIGN KEY(job_id) REFERENCES jobs(id)
        );

CREATE TABLE cue_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL,
        visit_type TEXT NOT NULL,
        due_date TEXT NOT NULL,
        time_window_start TEXT,
        time_window_end TEXT,
        priority TEXT NOT NULL DEFAULT 'Normal',
        status TEXT NOT NULL DEFAULT 'Pending',
        assigned_user_id INTEGER,
        instructions TEXT,
        created_by_user_id INTEGER,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        completed_at TEXT, cue_link TEXT, cue_status TEXT DEFAULT 'open',
        FOREIGN KEY(job_id) REFERENCES jobs(id),
        FOREIGN KEY(assigned_user_id) REFERENCES users(id),
        FOREIGN KEY(created_by_user_id) REFERENCES users(id)
    );

CREATE TABLE customer_addresses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            address TEXT NOT NULL,
            label TEXT NOT NULL DEFAULT 'Primary',
            is_primary INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY(customer_id) REFERENCES customers(id)
        );

CREATE TABLE customer_companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            company_name TEXT NOT NULL,
            is_primary INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY(customer_id) REFERENCES customers(id)
        );

CREATE TABLE customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        company TEXT,
        email TEXT,
        dob TEXT,
        address TEXT,
        notes TEXT,
        id_image_filename TEXT,
        id_image_path TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL DEFAULT ''
    , role TEXT);

CREATE TABLE document_extractions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pending_upload_id INTEGER,
        status TEXT NOT NULL DEFAULT 'success',
        provider_used TEXT NOT NULL DEFAULT 'rule_based',
        extracted_json TEXT NOT NULL,
        extracted_text TEXT,
        created_at TEXT NOT NULL
    );

CREATE TABLE form_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            field_list TEXT NOT NULL,
            created_by INTEGER,
            created_at TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1
        );

CREATE TABLE interactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL,
        event_type TEXT NOT NULL,
        narrative TEXT NOT NULL,
        occurred_at TEXT NOT NULL,
        created_at TEXT NOT NULL, photo_path TEXT,
        FOREIGN KEY(job_id) REFERENCES jobs(id)
    );

CREATE TABLE job_assets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL,
        asset_type TEXT NOT NULL DEFAULT 'Other',
        description TEXT,
        rego TEXT,
        vin TEXT,
        make TEXT,
        model TEXT,
        year TEXT,
        address TEXT,
        serial TEXT,
        notes TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(job_id) REFERENCES jobs(id)
    );

CREATE TABLE job_customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            customer_id INTEGER NOT NULL,
            role TEXT NOT NULL DEFAULT 'Primary',
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            UNIQUE(job_id, customer_id)
        );

CREATE TABLE job_documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL,
        doc_type TEXT NOT NULL,
        title TEXT,
        original_filename TEXT NOT NULL,
        stored_filename TEXT NOT NULL,
        mime_type TEXT,
        file_size INTEGER,
        uploaded_by_user_id INTEGER,
        uploaded_at TEXT NOT NULL,
        notes TEXT, file_status TEXT DEFAULT 'ok',
        FOREIGN KEY(job_id) REFERENCES jobs(id),
        FOREIGN KEY(uploaded_by_user_id) REFERENCES users(id)
    );

CREATE TABLE job_field_notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL,
        created_by_user_id INTEGER,
        note_text TEXT,
        created_at TEXT NOT NULL, note_type TEXT NOT NULL DEFAULT 'text', audio_filename TEXT, note_category TEXT DEFAULT 'file_note', review_status TEXT DEFAULT 'published', source_field_note_id INTEGER, reviewed_by_user_id INTEGER, reviewed_at TEXT, published_at TEXT, updated_at TEXT, updated_by_user_id INTEGER,
        FOREIGN KEY(job_id) REFERENCES jobs(id),
        FOREIGN KEY(created_by_user_id) REFERENCES users(id)
    );

CREATE TABLE job_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL,

        item_type TEXT NOT NULL,
        description TEXT,

        reg TEXT,
        vin TEXT,
        make TEXT,
        model TEXT,
        year TEXT,

        property_address TEXT,
        lot_details TEXT,

        serial_number TEXT,
        identifier TEXT,

        notes TEXT,

        created_at TEXT NOT NULL, lender_name TEXT, account_number TEXT, regulation_type TEXT, engine_number TEXT, deliver_to TEXT, colour TEXT, arrears_cents INTEGER, costs_cents INTEGER,
        FOREIGN KEY(job_id) REFERENCES jobs(id)
    );

CREATE TABLE job_lifecycle_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    from_status TEXT,
    to_status TEXT,
    performed_by_user_id INTEGER,
    performed_at TEXT NOT NULL,
    notes TEXT,
    batch_id TEXT,
    FOREIGN KEY(job_id) REFERENCES jobs(id),
    FOREIGN KEY(performed_by_user_id) REFERENCES users(id)
);

CREATE TABLE job_note_files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_field_note_id INTEGER NOT NULL,
        filename TEXT NOT NULL,
        filepath TEXT NOT NULL,
        uploaded_at TEXT NOT NULL, file_status TEXT DEFAULT 'ok',
        FOREIGN KEY(job_field_note_id) REFERENCES job_field_notes(id)
    );

CREATE TABLE job_office_notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL,
        note_body TEXT NOT NULL,
        created_by_user_id INTEGER,
        created_at TEXT NOT NULL,
        updated_by_user_id INTEGER,
        updated_at TEXT,
        is_deleted INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY(job_id) REFERENCES jobs(id),
        FOREIGN KEY(created_by_user_id) REFERENCES users(id)
    );

CREATE TABLE job_payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL,
        payment_date TEXT NOT NULL,
        amount_cents INTEGER NOT NULL,
        note TEXT,
        recorded_by_user_id INTEGER,
        created_at TEXT NOT NULL,
        FOREIGN KEY(job_id) REFERENCES jobs(id)
    );

CREATE TABLE job_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            active INTEGER NOT NULL DEFAULT 1
        );

CREATE TABLE job_update_photos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_update_id INTEGER NOT NULL,
        job_id INTEGER NOT NULL,
        filename TEXT NOT NULL,
        filepath TEXT NOT NULL,
        tag TEXT NOT NULL DEFAULT 'general',
        uploaded_at TEXT NOT NULL,
        FOREIGN KEY(job_update_id) REFERENCES job_updates(id),
        FOREIGN KEY(job_id) REFERENCES jobs(id)
    );

CREATE TABLE job_updates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL,
        created_by_user_id INTEGER,
        status TEXT NOT NULL DEFAULT 'draft',
        attend_date TEXT,
        attend_time TEXT,
        is_first_attendance INTEGER NOT NULL DEFAULT 0,
        property_description TEXT,
        security_sighted INTEGER NOT NULL DEFAULT 0,
        security_make_model TEXT,
        security_reg TEXT,
        security_location TEXT,
        calling_card INTEGER NOT NULL DEFAULT 0,
        neighbour_outcome TEXT,
        call_made INTEGER NOT NULL DEFAULT 0,
        call_outcome TEXT,
        voicemail_left INTEGER NOT NULL DEFAULT 0,
        sms_sent INTEGER NOT NULL DEFAULT 0,
        customer_mobile TEXT,
        points_of_contact INTEGER NOT NULL DEFAULT 0,
        eta_next_date TEXT,
        generated_narrative TEXT,
        final_narrative TEXT,
        narrative_edited INTEGER NOT NULL DEFAULT 0,
        structured_inputs_json TEXT,
        ai_model_used TEXT,
        ai_tokens_used INTEGER,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL, notes_text TEXT, notes_extracted_json TEXT, conflict_flag INTEGER DEFAULT 0, conflict_details TEXT, neighbour_interaction INTEGER DEFAULT 0, neighbour_result TEXT, photos_count INTEGER NOT NULL DEFAULT 0, agent_notes TEXT DEFAULT '', is_ai_draft INTEGER NOT NULL DEFAULT 1,
        FOREIGN KEY(job_id) REFERENCES jobs(id),
        FOREIGN KEY(created_by_user_id) REFERENCES users(id)
    );

CREATE TABLE jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,

        internal_job_number TEXT NOT NULL,
        client_reference TEXT,
        display_ref TEXT NOT NULL,

        client_id INTEGER,
        customer_id INTEGER,
        assigned_user_id INTEGER,

        job_type TEXT NOT NULL,
        visit_type TEXT NOT NULL,
        status TEXT NOT NULL,
        priority TEXT NOT NULL,

        job_address TEXT,
        description TEXT,

        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL, lender_name TEXT, account_number TEXT, regulation_type TEXT, arrears_cents INTEGER, costs_cents INTEGER, mmp_cents INTEGER, job_due_date TEXT, bill_to_client_id INTEGER, payment_frequency TEXT, client_job_number TEXT, deliver_to TEXT, lat REAL, lng REAL, is_regional INTEGER, confirmed_skip INTEGER, costs2_cents INTEGER, tp_referral TEXT, tp_job_number TEXT, geoop_source_description TEXT, geoop_job_id TEXT, archived_at TEXT, archived_by_user_id INTEGER, cold_stored_at TEXT, cold_stored_by_user_id INTEGER, cold_storage_ref TEXT, lifecycle_status TEXT DEFAULT 'active', geocode_fail INTEGER DEFAULT 0, geoop_assigned_agent TEXT, status_changed_at TEXT, last_client_update_request_sent_at TEXT, client_update_request_count INTEGER DEFAULT 0,

        FOREIGN KEY(client_id) REFERENCES clients(id),
        FOREIGN KEY(customer_id) REFERENCES customers(id),
        FOREIGN KEY(assigned_user_id) REFERENCES users(id)
    );

CREATE TABLE login_throttle (
  key TEXT PRIMARY KEY,
  fail_count INTEGER NOT NULL DEFAULT 0,
  locked_until TEXT,
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE lpr_audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            user_role TEXT NOT NULL,
            searched_registration TEXT NOT NULL,
            normalised_registration TEXT NOT NULL,
            result_type TEXT NOT NULL,
            matched_job_id INTEGER,
            matched_job_number TEXT,
            is_allocated_to_user INTEGER DEFAULT 0,
            search_method TEXT DEFAULT 'manual',
            created_at TEXT NOT NULL
        );

CREATE TABLE lpr_device_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            platform TEXT DEFAULT 'ios',
            token TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL, environment TEXT, active INTEGER NOT NULL DEFAULT 1, last_seen_at TEXT,
            UNIQUE(user_id, token)
        );

CREATE TABLE lpr_patrol_intelligence (
            id                          INTEGER PRIMARY KEY AUTOINCREMENT,
            registration_normalised     TEXT    NOT NULL UNIQUE,
            matched_job_id              INTEGER,
            repeat_count_30d            INTEGER NOT NULL DEFAULT 0,
            distinct_agent_count        INTEGER NOT NULL DEFAULT 0,
            likely_zone                 TEXT,
            likely_day_bucket           TEXT,
            likely_time_window          TEXT,
            confidence_score            INTEGER NOT NULL DEFAULT 0,
            recommended_patrol_priority TEXT    DEFAULT 'low',
            recommended_action          TEXT,
            explanation                 TEXT,
            watchlist_hit               INTEGER DEFAULT 0,
            result_type                 TEXT,
            last_computed_at            TEXT    NOT NULL
        );

CREATE TABLE lpr_prediction_scores (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            registration_normalised TEXT    NOT NULL UNIQUE,
            matched_job_id          INTEGER,
            rule_confidence_score   INTEGER NOT NULL DEFAULT 0,
            ml_confidence_score     INTEGER,
            combined_score          INTEGER NOT NULL DEFAULT 0,
            prediction_window       TEXT    DEFAULT '72h',
            model_version           TEXT    DEFAULT 'unscored',
            last_scored_at          TEXT    NOT NULL
        , blend_rule_weight REAL, blend_ml_weight REAL, ranking_config_id INTEGER, experiment_id INTEGER, experiment_arm TEXT);

CREATE TABLE lpr_sightings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            registration_raw TEXT NOT NULL,
            registration_normalised TEXT NOT NULL,
            search_method TEXT DEFAULT 'live_scan',
            result_type TEXT NOT NULL,
            matched_job_id INTEGER,
            matched_job_number TEXT,
            latitude REAL,
            longitude REAL,
            photo_path TEXT,
            notes TEXT,
            escalated_to_office INTEGER DEFAULT 0,
            watchlist_hit INTEGER DEFAULT 0,
            reviewed INTEGER DEFAULT 0,
            reviewed_by INTEGER,
            reviewed_at TEXT,
            office_note TEXT,
            follow_up_status TEXT,
            client_action_id TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );

CREATE TABLE lpr_watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            registration TEXT NOT NULL,
            registration_normalised TEXT NOT NULL,
            matched_job_id INTEGER,
            reason TEXT,
            priority TEXT DEFAULT 'normal',
            active INTEGER DEFAULT 1,
            created_by INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY(matched_job_id) REFERENCES jobs(id),
            FOREIGN KEY(created_by) REFERENCES users(id)
        );

CREATE TABLE message_audit_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id      INTEGER,
    actual_sender_id INTEGER,
    display_sender  TEXT,
    recipients      TEXT,
    job_id          INTEGER,
    action_type     TEXT    NOT NULL DEFAULT 'system_message',
    body_preview    TEXT,
    created_at      TEXT    NOT NULL
);

CREATE TABLE message_notification_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER NOT NULL,
            recipient_user_id INTEGER NOT NULL,
            token_id INTEGER,
            status TEXT NOT NULL,
            error TEXT,
            sent_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(message_id, recipient_user_id, token_id)
        );

CREATE TABLE message_reads (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER NOT NULL,
            user_id    INTEGER NOT NULL,
            read_at    TEXT    NOT NULL,
            UNIQUE(message_id, user_id),
            FOREIGN KEY(message_id) REFERENCES messages(id),
            FOREIGN KEY(user_id)    REFERENCES users(id)
        );

CREATE TABLE messages (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            sender_id       INTEGER NOT NULL,
            body            TEXT    NOT NULL,
            created_at      TEXT    NOT NULL,
            is_deleted      INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(conversation_id) REFERENCES conversations(id),
            FOREIGN KEY(sender_id)       REFERENCES users(id)
        );

CREATE TABLE mobile_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER, action TEXT, record_type TEXT,
            record_id INTEGER, created_at TEXT
        );

CREATE TABLE mobile_auth_tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token TEXT NOT NULL UNIQUE,
        user_id INTEGER NOT NULL,
        device_name TEXT,
        created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        revoked_at TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );

CREATE TABLE password_reset_tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        token TEXT NOT NULL UNIQUE,
        expires_at TEXT NOT NULL,
        used INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );

CREATE TABLE pending_uploads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        original_filename TEXT NOT NULL,
        storage_key TEXT NOT NULL,
        content_type TEXT,
        uploaded_by_user_id INTEGER,
        uploaded_at TEXT NOT NULL
    );

CREATE TABLE recovery_target_addresses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_id INTEGER NOT NULL,
            address_type TEXT,
            full_address TEXT,
            suburb TEXT,
            state TEXT,
            postcode TEXT,
            notes TEXT,
            is_primary INTEGER DEFAULT 0,
            FOREIGN KEY(target_id) REFERENCES recovery_targets(id)
        );

CREATE TABLE recovery_target_asset_reg_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id INTEGER NOT NULL,
            registration_number TEXT,
            notes TEXT,
            FOREIGN KEY(asset_id) REFERENCES recovery_target_assets(id)
        );

CREATE TABLE recovery_target_assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_id INTEGER NOT NULL,
            asset_type TEXT,
            make TEXT,
            model TEXT,
            year TEXT,
            colour TEXT,
            registration_number TEXT,
            vin TEXT,
            engine_number TEXT,
            contract_number TEXT,
            distinguishing_features TEXT,
            accessories TEXT,
            current_security_status TEXT,
            operational_notes TEXT,
            is_primary_asset INTEGER DEFAULT 0,
            FOREIGN KEY(target_id) REFERENCES recovery_targets(id)
        );

CREATE TABLE recovery_target_associates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_id INTEGER NOT NULL,
            full_name TEXT,
            relationship TEXT,
            phone TEXT,
            address TEXT,
            notes TEXT,
            FOREIGN KEY(target_id) REFERENCES recovery_targets(id)
        );

CREATE TABLE recovery_target_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_id INTEGER NOT NULL,
            asset_id INTEGER,
            document_type TEXT,
            category TEXT,
            original_filename TEXT NOT NULL,
            stored_filename TEXT NOT NULL,
            content_type TEXT,
            uploaded_at TEXT NOT NULL,
            uploaded_by INTEGER,
            description TEXT,
            FOREIGN KEY(target_id) REFERENCES recovery_targets(id),
            FOREIGN KEY(asset_id) REFERENCES recovery_target_assets(id)
        );

CREATE TABLE recovery_target_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_id INTEGER NOT NULL,
            note_type TEXT,
            note_text TEXT NOT NULL,
            created_at TEXT NOT NULL,
            created_by INTEGER,
            FOREIGN KEY(target_id) REFERENCES recovery_targets(id)
        );

CREATE TABLE recovery_target_parties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_id INTEGER NOT NULL,
            party_type TEXT,
            organisation_name TEXT,
            contact_person TEXT,
            phone TEXT,
            email TEXT,
            reference_number TEXT,
            notes TEXT,
            FOREIGN KEY(target_id) REFERENCES recovery_targets(id)
        );

CREATE TABLE recovery_target_people (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_id INTEGER NOT NULL,
            full_legal_name TEXT,
            aliases TEXT,
            date_of_birth TEXT,
            driver_licence_number TEXT,
            licence_state TEXT,
            email_primary TEXT,
            risk_notes TEXT,
            general_notes TEXT,
            FOREIGN KEY(target_id) REFERENCES recovery_targets(id)
        );

CREATE TABLE recovery_target_phones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_id INTEGER NOT NULL,
            phone_number TEXT,
            label TEXT,
            is_primary INTEGER DEFAULT 0,
            FOREIGN KEY(target_id) REFERENCES recovery_targets(id)
        );

CREATE TABLE recovery_targets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ref TEXT NOT NULL UNIQUE,
        status TEXT NOT NULL DEFAULT 'Active',
        record_type TEXT NOT NULL DEFAULT 'LPR Repossession Record',
        agency_name TEXT, agency_contact TEXT, agency_phone TEXT,
        agency_email TEXT, agency_ref TEXT,
        lender_name TEXT, lender_contact TEXT, lender_phone TEXT,
        lender_email TEXT, lender_ref TEXT,
        liquidator_name TEXT, liquidator_contact TEXT, liquidator_phone TEXT,
        liquidator_email TEXT, liquidator_ref TEXT,
        customer_full_name TEXT,
        customer_aliases TEXT,
        customer_dob TEXT,
        customer_dl_number TEXT,
        customer_dl_state TEXT,
        customer_email TEXT,
        caution_notes TEXT,
        repossessed_at TEXT,
        repossession_note TEXT,
        assigned_user_id INTEGER,
        created_by_user_id INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL, created_by INTEGER, updated_by INTEGER, assigned_agency TEXT, assigned_staff_user_id INTEGER, internal_reference TEXT, agency_reference TEXT, lender_reference TEXT, liquidator_reference TEXT, repossession_active INTEGER NOT NULL DEFAULT 1, repossession_completed_at TEXT, outcome_note TEXT,
        FOREIGN KEY(assigned_user_id) REFERENCES users(id),
        FOREIGN KEY(created_by_user_id) REFERENCES users(id)
    );

CREATE TABLE repo_lock_queue (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id                INTEGER NOT NULL,
    item_id               INTEGER NOT NULL,
    repo_lock_id          INTEGER NOT NULL,
    status                TEXT NOT NULL DEFAULT 'Pending',
    submission_count      INTEGER NOT NULL DEFAULT 1,
    submitted_at          TEXT NOT NULL,
    submitted_by_user_id  INTEGER,
    reviewed_by_user_id   INTEGER,
    reviewed_at           TEXT,
    notes                 TEXT,
    created_at            TEXT NOT NULL,
    updated_at            TEXT NOT NULL,
    FOREIGN KEY(job_id)       REFERENCES jobs(id),
    FOREIGN KEY(repo_lock_id) REFERENCES repo_lock_records(id)
);

CREATE TABLE repo_lock_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id  INTEGER NOT NULL,
        item_id INTEGER NOT NULL,
        client_name               TEXT,
        client_reference          TEXT,
        swpi_ref                  TEXT,
        finance_company           TEXT,
        repo_date                 TEXT,
        start_time                TEXT,
        end_time                  TEXT,
        customer_name             TEXT,
        account_number            TEXT,
        repo_address              TEXT,
        repossession_address      TEXT,
        contact_number            TEXT,
        description               TEXT,
        registration              TEXT,
        rego_expiry               TEXT,
        registered                TEXT,
        insured                   TEXT,
        insured_with              TEXT,
        vin                       TEXT,
        engine_number             TEXT,
        speedometer               TEXT,
        person_present            TEXT,
        keys_obtained             TEXT,
        how_many_keys             TEXT,
        vol_surrender             TEXT,
        form_13                   TEXT,
        form_13_signed_by         TEXT,
        repossessed_from          TEXT,
        lien_paid                 TEXT,
        security_drivable         TEXT,
        police_notified           TEXT,
        station_officer           TEXT,
        personal_effects_removed  TEXT,
        removed_by_who            TEXT,
        personal_effects_list     TEXT,
        tyres                     TEXT,
        body                      TEXT,
        duco                      TEXT,
        interior                  TEXT,
        engine_condition          TEXT,
        transmission              TEXT,
        fuel_level                TEXT,
        any_damage                TEXT,
        damage_list               TEXT,
        tow_company_id            INTEGER,
        tow_company_name          TEXT,
        tow_costs                 TEXT,
        deliver_to                TEXT,
        delivery_address          TEXT,
        expected_delivery_date    TEXT,
        customers_intention       TEXT,
        other_info                TEXT,
        agent_name                TEXT,
        agent_user_id             INTEGER,
        created_by_user_id        INTEGER,
        created_at                TEXT NOT NULL,
        updated_by_user_id        INTEGER,
        updated_at                TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Draft', submitted_at TEXT, agent_signature TEXT, customer_signature TEXT, tow_signature TEXT, agent_signed_at TEXT, customer_signed_at TEXT, tow_signed_at TEXT, make TEXT, model TEXT, year TEXT, notice_delivered_by TEXT, notice_delivery TEXT, tow_phone TEXT,
        FOREIGN KEY(job_id)  REFERENCES jobs(id),
        FOREIGN KEY(item_id) REFERENCES job_items(id)
    );

CREATE TABLE route_plan_stops (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        route_plan_id INTEGER NOT NULL,
        job_id INTEGER,
        stop_order INTEGER NOT NULL,
        suburb TEXT,
        address TEXT,
        lat REAL,
        lng REAL,
        distance_from_previous_meters REAL,
        duration_from_previous_seconds REAL,
        eta TEXT,
        is_pinned_start INTEGER NOT NULL DEFAULT 0,
        is_pinned_end INTEGER NOT NULL DEFAULT 0,
        navigation_url TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(route_plan_id) REFERENCES route_plans(id),
        FOREIGN KEY(job_id) REFERENCES jobs(id)
    );

CREATE TABLE route_plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_by_user_id INTEGER NOT NULL,
        assigned_agent_id INTEGER,
        name TEXT,
        route_mode TEXT NOT NULL DEFAULT 'full_optimise',
        direction_mode TEXT NOT NULL DEFAULT 'forward',
        start_type TEXT NOT NULL DEFAULT 'office',
        start_address TEXT,
        start_lat REAL,
        start_lng REAL,
        end_type TEXT,
        end_address TEXT,
        end_lat REAL,
        end_lng REAL,
        pinned_first_job_id INTEGER,
        pinned_last_job_id INTEGER,
        total_distance_meters REAL,
        total_duration_seconds REAL,
        suburb_sequence_json TEXT,
        status TEXT NOT NULL DEFAULT 'draft',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(created_by_user_id) REFERENCES users(id)
    );

CREATE TABLE rt_addresses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        target_id INTEGER NOT NULL,
        address_type TEXT DEFAULT 'Residential',
        address_line TEXT NOT NULL,
        suburb TEXT, state TEXT, postcode TEXT,
        is_last_known INTEGER DEFAULT 0,
        notes TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(target_id) REFERENCES recovery_targets(id)
    );

CREATE TABLE rt_documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        target_id INTEGER NOT NULL,
        doc_category TEXT DEFAULT 'Other',
        doc_title TEXT,
        original_filename TEXT NOT NULL,
        stored_filename TEXT NOT NULL,
        mime_type TEXT,
        file_size INTEGER,
        uploaded_by_user_id INTEGER,
        uploaded_at TEXT NOT NULL,
        notes TEXT,
        FOREIGN KEY(target_id) REFERENCES recovery_targets(id),
        FOREIGN KEY(uploaded_by_user_id) REFERENCES users(id)
    );

CREATE TABLE rt_notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        target_id INTEGER NOT NULL,
        note_type TEXT DEFAULT 'General',
        body TEXT NOT NULL,
        created_by_user_id INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(target_id) REFERENCES recovery_targets(id),
        FOREIGN KEY(created_by_user_id) REFERENCES users(id)
    );

CREATE TABLE rt_phones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        target_id INTEGER NOT NULL,
        phone_type TEXT DEFAULT 'Mobile',
        phone_number TEXT NOT NULL,
        notes TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(target_id) REFERENCES recovery_targets(id)
    );

CREATE TABLE rt_securities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        target_id INTEGER NOT NULL,
        asset_type TEXT DEFAULT 'Vehicle',
        make TEXT, model TEXT, year TEXT, colour TEXT,
        reg TEXT, reg_normalised TEXT,
        prev_regs TEXT,
        vin TEXT,
        engine_number TEXT,
        contract_number TEXT,
        distinguishing_features TEXT,
        accessories TEXT,
        current_status TEXT,
        operational_notes TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(target_id) REFERENCES recovery_targets(id)
    );

CREATE TABLE schedule_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        schedule_id INTEGER NOT NULL,
        job_id INTEGER NOT NULL,
        action TEXT NOT NULL,
        old_scheduled_for TEXT,
        new_scheduled_for TEXT,
        old_status TEXT,
        new_status TEXT,
        changed_by_user_id INTEGER,
        created_at TEXT NOT NULL,
        notes TEXT,
        FOREIGN KEY(schedule_id) REFERENCES schedules(id),
        FOREIGN KEY(job_id) REFERENCES jobs(id),
        FOREIGN KEY(changed_by_user_id) REFERENCES users(id)
    );

CREATE TABLE schedules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL,
        booking_type_id INTEGER NOT NULL,
        scheduled_for TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Booked',
        notes TEXT,
        created_by_user_id INTEGER,
        created_at TEXT NOT NULL, assigned_to_user_id INTEGER, hidden INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY(job_id) REFERENCES jobs(id),
        FOREIGN KEY(booking_type_id) REFERENCES booking_types(id),
        FOREIGN KEY(created_by_user_id) REFERENCES users(id)
    );

CREATE TABLE sqlite_sequence(name,seq);

CREATE TABLE system_settings (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        job_prefix TEXT NOT NULL,
        job_sequence INTEGER NOT NULL,
        auto_prefix_enabled INTEGER NOT NULL DEFAULT 1,
        updated_at TEXT NOT NULL
    , email_signature TEXT, openai_api_key TEXT, ai_use_own_key INTEGER, lpr_patrol_mode_enabled INTEGER DEFAULT 1, archive_after_days INTEGER DEFAULT 90, cold_store_after_years INTEGER DEFAULT 3, archive_mode TEXT DEFAULT 'manual', cold_storage_mode TEXT DEFAULT 'manual', allow_restore_to_active INTEGER DEFAULT 1, allow_permanent_delete INTEGER DEFAULT 0, archive_exclude_client_ids TEXT, office_address TEXT, office_lat REAL, office_lng REAL);

CREATE TABLE tow_operators (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL,
            phone TEXT,
            address TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        , contact_name TEXT, mobile TEXT, other_phone TEXT, email TEXT, suburb TEXT, state TEXT, postcode TEXT, notes TEXT, created_by_user_id INTEGER);

CREATE TABLE urgent_update_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL,
        sched_id INTEGER NOT NULL UNIQUE,
        triggered_by_user_id INTEGER NOT NULL,
        agent_user_id INTEGER NOT NULL,
        triggered_at TEXT NOT NULL,
        message_id INTEGER,
        note_id INTEGER,
        new_sched_id INTEGER,
        FOREIGN KEY(job_id) REFERENCES jobs(id)
    );

CREATE TABLE user_mobile_settings (
        user_id INTEGER PRIMARY KEY,
        list_sort TEXT NOT NULL DEFAULT 'visit_date',
        list_dir TEXT NOT NULL DEFAULT 'asc',
        distance_unit TEXT NOT NULL DEFAULT 'km',
        gps_foreground INTEGER NOT NULL DEFAULT 1,
        gps_bg INTEGER NOT NULL DEFAULT 0,
        gps_interval_mins INTEGER NOT NULL DEFAULT 5,
        updated_at TEXT
    , job_scope TEXT NOT NULL DEFAULT 'mine', show_completed TEXT NOT NULL DEFAULT 'week', quick_status TEXT NOT NULL DEFAULT '', mobile_default_view TEXT NOT NULL DEFAULT 'schedule', show_status_on_visits INTEGER NOT NULL DEFAULT 1, job_assignment TEXT NOT NULL DEFAULT 'all');

CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL,
        active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL
    , home_address TEXT, home_lat REAL, home_lng REAL);

CREATE INDEX idx_ca_cust ON customer_addresses(customer_id);

CREATE INDEX idx_cc_cust ON customer_companies(customer_id);

CREATE INDEX idx_cpn_entity ON contact_phone_numbers(entity_type, entity_id);

CREATE INDEX idx_cur_job ON client_update_requests(job_id, sent_at);

CREATE INDEX idx_int_job ON interactions(job_id);

CREATE INDEX idx_jfn_job ON job_field_notes(job_id);

CREATE INDEX idx_jfn_job_review ON job_field_notes(job_id, review_status);

CREATE INDEX idx_ji_job ON job_items(job_id);

CREATE INDEX idx_ji_job_type ON job_items(job_id, item_type);

CREATE INDEX idx_jll_job ON job_lifecycle_log(job_id);

CREATE UNIQUE INDEX idx_jnf_note_file ON job_note_files(job_field_note_id, filename);

CREATE INDEX idx_jnf_note_id ON job_note_files(job_field_note_id);

CREATE INDEX idx_jobs_assigned ON jobs(assigned_user_id);

CREATE INDEX idx_jobs_client ON jobs(client_id);

CREATE INDEX idx_jobs_customer ON jobs(customer_id);

CREATE INDEX idx_jobs_status ON jobs(status);

CREATE INDEX idx_jon_job ON job_office_notes(job_id, is_deleted);

CREATE INDEX idx_ju_job ON job_updates(job_id);

CREATE INDEX idx_lpr_device_tokens_user_active ON lpr_device_tokens(user_id, active);

CREATE INDEX idx_mal_job ON message_audit_log(job_id);

CREATE INDEX idx_msgs_conv ON messages(conversation_id, sender_id, is_deleted);

CREATE INDEX idx_recovery_assets_reg ON recovery_target_assets(registration_number);

CREATE INDEX idx_recovery_assets_vin ON recovery_target_assets(vin);

CREATE INDEX idx_recovery_people_name ON recovery_target_people(full_legal_name);

CREATE INDEX idx_recovery_reg_history_reg ON recovery_target_asset_reg_history(registration_number);

CREATE INDEX idx_recovery_targets_status ON recovery_targets(status, repossession_active);

CREATE INDEX idx_sched_assigned ON schedules(assigned_to_user_id);

CREATE INDEX idx_sched_job ON schedules(job_id);

CREATE INDEX idx_sched_job_status ON schedules(job_id, status, hidden);

CREATE INDEX idx_uul_job ON urgent_update_log(job_id);

CREATE INDEX idx_uul_sched ON urgent_update_log(sched_id);
