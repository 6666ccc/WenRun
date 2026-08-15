create table ai_knowledge_documents
(
    id             bigint auto_increment comment '??'
        primary key,
    document_id    varchar(64)   not null comment '????ID',
    knowledge_base varchar(32)   not null comment '?????',
    original_name  varchar(255)  not null comment '?????',
    storage_path   varchar(500)  not null comment '??????',
    content_type   varchar(100)  not null comment 'MIME??',
    file_size      bigint        not null comment '????',
    file_sha256    varchar(64)   not null comment '????',
    status         varchar(32)   not null comment 'PROCESSING/READY/FAILED/DELETING/DELETE_FAILED/DELETED',
    chunk_count    int default 0 not null comment '????',
    error_message  varchar(1000) null comment '????',
    uploaded_by    bigint        not null comment '?????ID',
    created_at     datetime      not null comment '????',
    updated_at     datetime      not null comment '????',
    completed_at   datetime      null comment '????',
    deleted_at     datetime      null comment '????',
    constraint uk_ai_knowledge_document_id
        unique (document_id)
)
    comment '????????';

create index idx_ai_knowledge_base_status
    on ai_knowledge_documents (knowledge_base, status);

create index idx_ai_knowledge_sha256
    on ai_knowledge_documents (knowledge_base, file_sha256);

create index idx_ai_knowledge_uploaded_by
    on ai_knowledge_documents (uploaded_by);

create table charge_detail
(
    id              bigint auto_increment comment '??'
        primary key,
    charge_order_id bigint                      not null comment '???ID',
    biz_type        tinyint                     not null comment '????',
    biz_id          bigint                      null comment '????ID',
    item_name       varchar(128)                not null comment '?????',
    amount          decimal(12, 2) default 0.00 not null comment '??'
)
    comment '????';

create index idx_charge_detail_biz
    on charge_detail (biz_type, biz_id);

create index idx_charge_detail_order_id
    on charge_detail (charge_order_id);

create table charge_order
(
    id           bigint auto_increment comment '??'
        primary key,
    order_no     varchar(64)                              not null comment '????',
    patient_id   bigint                                   not null comment '??ID',
    visit_id     bigint                                   null comment '??ID',
    total_amount decimal(12, 2) default 0.00              not null comment '????',
    paid_amount  decimal(12, 2) default 0.00              not null comment '????',
    pay_type     tinyint                                  null comment '????',
    pay_status   tinyint        default 0                 not null comment '???? 1???',
    cashier_id   bigint                                   null comment '???ID',
    pay_time     datetime                                 null comment '????',
    create_time  datetime       default CURRENT_TIMESTAMP not null comment '????',
    update_time  datetime       default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP comment '????',
    constraint uk_charge_order_no
        unique (order_no)
)
    comment '???';

create index idx_charge_order_patient_id
    on charge_order (patient_id);

create index idx_charge_order_pay_status
    on charge_order (pay_status);

create index idx_charge_order_visit_id
    on charge_order (visit_id);

create table chat_messages
(
    id              bigint auto_increment comment '??'
        primary key,
    conversation_id varchar(64)                        not null comment '??ID',
    user_id         bigint                             not null comment '?????ID',
    role            varchar(32)                        not null comment 'user/assistant',
    content         mediumtext                         not null comment '?????',
    create_time     datetime default CURRENT_TIMESTAMP not null comment '????'
)
    comment 'AI????';

create index idx_chat_messages_conversation_id
    on chat_messages (conversation_id);

create index idx_chat_messages_create_time
    on chat_messages (create_time);

create index idx_chat_messages_user_id
    on chat_messages (user_id);

create table dept
(
    id          bigint auto_increment comment '??'
        primary key,
    dept_code   varchar(64)                        not null comment '????',
    dept_name   varchar(128)                       not null comment '????',
    parent_id   bigint                             null comment '????ID',
    status      tinyint  default 1                 not null comment '??',
    create_time datetime default CURRENT_TIMESTAMP not null comment '????',
    update_time datetime default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP comment '????',
    constraint uk_dept_code
        unique (dept_code)
)
    comment '??';

create index idx_dept_parent_id
    on dept (parent_id);

create index idx_dept_status
    on dept (status);

create table dispense_record
(
    id              bigint auto_increment comment '??'
        primary key,
    prescription_id bigint            not null comment '??ID',
    pharmacist_id   bigint            null comment '????ID',
    dispense_time   datetime          null comment '????',
    status          tinyint default 0 not null comment '????'
)
    comment '????';

create index idx_dispense_record_pharmacist_id
    on dispense_record (pharmacist_id);

create index idx_dispense_record_prescription_id
    on dispense_record (prescription_id);

create table drug
(
    id           bigint auto_increment comment '??'
        primary key,
    drug_code    varchar(64)                              not null comment '????',
    drug_name    varchar(128)                             not null comment '????',
    spec         varchar(128)                             null comment '??',
    unit         varchar(32)                              null comment '??',
    price        decimal(12, 2) default 0.00              not null comment '??',
    manufacturer varchar(128)                             null comment '??',
    status       tinyint        default 1                 not null comment '??',
    create_time  datetime       default CURRENT_TIMESTAMP not null comment '????',
    update_time  datetime       default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP comment '????',
    constraint uk_drug_code
        unique (drug_code)
)
    comment '??';

create index idx_drug_name
    on drug (drug_name);

create index idx_drug_status
    on drug (status);

create table drug_stock
(
    id            bigint auto_increment comment '??'
        primary key,
    drug_id       bigint                                   not null comment '??ID',
    quantity      decimal(12, 2) default 0.00              not null comment '????',
    warn_quantity decimal(12, 2) default 0.00              not null comment '????',
    update_time   datetime       default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP comment '????',
    constraint uk_drug_stock_drug_id
        unique (drug_id)
)
    comment '????';

create table exam_request
(
    id          bigint auto_increment comment '??'
        primary key,
    request_no  varchar(64)                              not null comment '????',
    visit_id    bigint                                   not null comment '??ID',
    patient_id  bigint                                   not null comment '??ID',
    item_id     bigint                                   not null comment '??ID',
    amount      decimal(12, 2) default 0.00              not null comment '??',
    status      tinyint        default 0                 not null comment '??',
    create_time datetime       default CURRENT_TIMESTAMP not null comment '????',
    update_time datetime       default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP comment '????',
    constraint uk_exam_request_no
        unique (request_no)
)
    comment '??????';

create index idx_exam_request_item_id
    on exam_request (item_id);

create index idx_exam_request_patient_id
    on exam_request (patient_id);

create index idx_exam_request_status
    on exam_request (status);

create index idx_exam_request_visit_id
    on exam_request (visit_id);

create table medical_item
(
    id          bigint auto_increment comment '??'
        primary key,
    item_code   varchar(64)                              not null comment '????',
    item_name   varchar(128)                             not null comment '????',
    item_type   tinyint                                  not null comment '????',
    price       decimal(12, 2) default 0.00              not null comment '??',
    dept_id     bigint                                   null comment '????ID',
    status      tinyint        default 1                 not null comment '??',
    create_time datetime       default CURRENT_TIMESTAMP not null comment '????',
    update_time datetime       default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP comment '????',
    constraint uk_medical_item_code
        unique (item_code)
)
    comment '????';

create index idx_medical_item_dept_id
    on medical_item (dept_id);

create index idx_medical_item_status
    on medical_item (status);

create index idx_medical_item_type
    on medical_item (item_type);

create table oauth_token_blacklist
(
    jti        varchar(64) not null comment 'JWT ID'
        primary key,
    expires_at datetime    not null comment '????'
)
    comment 'Token???';

create index idx_oauth_token_blacklist_expires_at
    on oauth_token_blacklist (expires_at);

create table outpatient_visit
(
    id              bigint auto_increment comment '??'
        primary key,
    visit_no        varchar(64)                        not null comment '???',
    registration_id bigint                             not null comment '??ID',
    patient_id      bigint                             not null comment '??ID',
    staff_id        bigint                             not null comment '??ID',
    visit_time      datetime                           null comment '????',
    chief_complaint varchar(500)                       null comment '??',
    diagnosis       varchar(500)                       null comment '??',
    status          tinyint  default 0                 not null comment '????',
    create_time     datetime default CURRENT_TIMESTAMP not null comment '????',
    update_time     datetime default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP comment '????',
    constraint uk_outpatient_visit_no
        unique (visit_no)
)
    comment '????';

create index idx_outpatient_visit_patient_id
    on outpatient_visit (patient_id);

create index idx_outpatient_visit_registration_id
    on outpatient_visit (registration_id);

create index idx_outpatient_visit_staff_id
    on outpatient_visit (staff_id);

create index idx_outpatient_visit_status
    on outpatient_visit (status);

create table patient
(
    id              bigint auto_increment comment '??'
        primary key,
    patient_no      varchar(64)                        not null comment '????',
    name            varchar(64)                        not null comment '??',
    gender          tinyint                            null comment '0? 1? 2??',
    birth_date      date                               null comment '????',
    id_card         varchar(32)                        null comment '????',
    phone           varchar(20)                        null comment '???',
    user_id         bigint                             null comment '???????',
    allergy_history varchar(500)                       null comment '???',
    address         varchar(255)                       null comment '??',
    create_time     datetime default CURRENT_TIMESTAMP not null comment '????',
    update_time     datetime default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP comment '????',
    constraint uk_patient_no
        unique (patient_no)
)
    comment '??';

create index idx_patient_id_card
    on patient (id_card);

create index idx_patient_phone
    on patient (phone);

create index idx_patient_user_id
    on patient (user_id);

create table prescription
(
    id           bigint auto_increment comment '??'
        primary key,
    rx_no        varchar(64)                              not null comment '???',
    visit_id     bigint                                   not null comment '??ID',
    patient_id   bigint                                   not null comment '??ID',
    staff_id     bigint                                   not null comment '????ID',
    total_amount decimal(12, 2) default 0.00              not null comment '????',
    status       tinyint        default 0                 not null comment '?? 2????',
    create_time  datetime       default CURRENT_TIMESTAMP not null comment '????',
    update_time  datetime       default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP comment '????',
    constraint uk_prescription_rx_no
        unique (rx_no)
)
    comment '??';

create index idx_prescription_patient_id
    on prescription (patient_id);

create index idx_prescription_staff_id
    on prescription (staff_id);

create index idx_prescription_status
    on prescription (status);

create index idx_prescription_visit_id
    on prescription (visit_id);

create table prescription_item
(
    id              bigint auto_increment comment '??'
        primary key,
    prescription_id bigint                      not null comment '??ID',
    drug_id         bigint                      not null comment '??ID',
    quantity        decimal(12, 2) default 0.00 not null comment '??',
    unit_price      decimal(12, 2) default 0.00 not null comment '??',
    amount          decimal(12, 2) default 0.00 not null comment '??',
    usage_desc      varchar(255)                null comment '????'
)
    comment '????';

create index idx_prescription_item_drug_id
    on prescription_item (drug_id);

create index idx_prescription_item_rx_id
    on prescription_item (prescription_id);

create table registration
(
    id                 bigint auto_increment comment '??'
        primary key,
    reg_no             varchar(64)                              not null comment '????',
    patient_id         bigint                                   not null comment '??ID',
    schedule_id        bigint                                   not null comment '??ID',
    dept_id            bigint                                   not null comment '??ID',
    staff_id           bigint                                   not null comment '??ID',
    reg_time           datetime                                 not null comment '????',
    reg_fee            decimal(12, 2) default 0.00              not null comment '???',
    status             tinyint        default 0                 not null comment '????',
    cashier_id         bigint                                   null comment '???ID',
    registrant_user_id bigint                                   null comment '??????ID',
    create_time        datetime       default CURRENT_TIMESTAMP not null comment '????',
    update_time        datetime       default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP comment '????',
    constraint uk_registration_reg_no
        unique (reg_no)
)
    comment '??';

create index idx_registration_patient_id
    on registration (patient_id);

create index idx_registration_registrant_user_id
    on registration (registrant_user_id);

create index idx_registration_schedule_id
    on registration (schedule_id);

create index idx_registration_staff_id
    on registration (staff_id);

create index idx_registration_status
    on registration (status);

create table schedule
(
    id              bigint auto_increment comment '??'
        primary key,
    dept_id         bigint                                   not null comment '??ID',
    staff_id        bigint                                   not null comment '??ID',
    work_date       date                                     not null comment '????',
    time_period     varchar(32)                              not null comment '??',
    total_count     int            default 0                 not null comment '???',
    remaining_count int            default 0                 not null comment '????',
    register_fee    decimal(12, 2) default 0.00              not null comment '???',
    create_time     datetime       default CURRENT_TIMESTAMP not null comment '????',
    update_time     datetime       default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP comment '????'
)
    comment '????';

create index idx_schedule_dept_id
    on schedule (dept_id);

create index idx_schedule_staff_date
    on schedule (staff_id, work_date);

create index idx_schedule_staff_id
    on schedule (staff_id);

create index idx_schedule_work_date
    on schedule (work_date);

create table staff
(
    id          bigint auto_increment comment '??'
        primary key,
    staff_no    varchar(64)                        not null comment '??',
    name        varchar(64)                        not null comment '??',
    dept_id     bigint                             null comment '??ID',
    title       varchar(64)                        null comment '??',
    user_id     bigint                             null comment '??????',
    status      tinyint  default 1                 not null comment '??',
    create_time datetime default CURRENT_TIMESTAMP not null comment '????',
    update_time datetime default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP comment '????',
    constraint uk_staff_no
        unique (staff_no)
)
    comment '????';

create index idx_staff_dept_id
    on staff (dept_id);

create index idx_staff_status
    on staff (status);

create index idx_staff_user_id
    on staff (user_id);

create table sys_role
(
    id             bigint auto_increment comment '??'
        primary key,
    role_code      varchar(64)                        not null comment '????',
    role_name      varchar(64)                        not null comment '????',
    default_portal varchar(32)                        null comment '???? admin/doctor/patient',
    create_time    datetime default CURRENT_TIMESTAMP not null comment '????',
    update_time    datetime default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP comment '????',
    constraint uk_sys_role_code
        unique (role_code)
)
    comment '????';

create table sys_user
(
    id             bigint auto_increment comment '??'
        primary key,
    username       varchar(64)                        not null comment '???',
    password       varchar(255)                       not null comment '????',
    real_name      varchar(64)                        null comment '????',
    phone          varchar(20)                        null comment '???',
    phone_verified tinyint  default 0                 not null comment '0??? 1???',
    account_type   varchar(32)                        not null comment 'internal/staff/patient',
    status         tinyint  default 1                 not null comment '????',
    create_time    datetime default CURRENT_TIMESTAMP not null comment '????',
    update_time    datetime default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP comment '????',
    constraint uk_sys_user_username
        unique (username)
)
    comment '????';

create index idx_sys_user_account_type
    on sys_user (account_type);

create index idx_sys_user_phone
    on sys_user (phone);

create table sys_user_role
(
    user_id bigint not null comment '??ID',
    role_id bigint not null comment '??ID',
    primary key (user_id, role_id)
)
    comment '??????';

create index idx_sys_user_role_role_id
    on sys_user_role (role_id);

