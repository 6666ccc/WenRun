package com.wenrun.ai.controller;

import com.wenrun.ai.security.DelegatedToolContext;
import com.wenrun.ai.security.DelegatedToolPrincipal;
import com.wenrun.ai.service.AiPatientMemoryService;
import com.wenrun.ai.service.PatientClinicalContextService;
import com.wenrun.ai.vo.PatientClinicalContextVO;
import com.wenrun.ai.vo.AiMemoryWriteRequest;
import com.wenrun.ai.vo.AiRegistrationCreateRequest;
import com.wenrun.common.constant.AccountType;
import com.wenrun.common.constant.BizStatus;
import com.wenrun.common.exception.BusinessException;
import com.wenrun.dto.RegistrationCreateDTO;
import com.wenrun.entity.ChatMessage;
import com.wenrun.entity.Dept;
import com.wenrun.entity.Staff;
import com.wenrun.repository.ChatMessageRepository;
import com.wenrun.service.DeptService;
import com.wenrun.service.RegistrationService;
import com.wenrun.service.ScheduleService;
import com.wenrun.service.StaffService;
import com.wenrun.vo.RegistrationVO;
import com.wenrun.vo.ScheduleVO;
import com.wenrun.vo.StaffVO;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import java.time.LocalDate;
import java.util.List;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

class AiToolControllerTest {

    private final DeptService deptService = mock(DeptService.class);
    private final ScheduleService scheduleService = mock(ScheduleService.class);
    private final StaffService staffService = mock(StaffService.class);
    private final RegistrationService registrationService = mock(RegistrationService.class);
    private final AiPatientMemoryService memoryService = mock(AiPatientMemoryService.class);
    private final ChatMessageRepository chatMessageRepository = mock(ChatMessageRepository.class);
    private final PatientClinicalContextService clinicalContextService = mock(PatientClinicalContextService.class);
    private final AiToolController controller =
            new AiToolController(deptService, scheduleService, staffService, registrationService,
                    memoryService, chatMessageRepository, clinicalContextService);

    @AfterEach
    void clearContext() {
        DelegatedToolContext.clear();
    }

    @Test
    void departmentsToolUsesJavaServiceAfterScopeCheck() {
        Dept dept = new Dept();
        dept.setId(1L);
        dept.setDeptName("内科");
        when(deptService.list(1)).thenReturn(List.of(dept));
        DelegatedToolContext.set(new DelegatedToolPrincipal(7L, 11L, "patient",
                Set.of("departments:read"), "token-1"));

        List<Dept> departments = controller.listDepartments(1).getData();

        assertEquals("内科", departments.getFirst().getDeptName());
        verify(deptService).list(1);
    }

    @Test
    void departmentDetailToolUsesJavaServiceAfterScopeCheck() {
        Dept dept = new Dept();
        dept.setId(3L);
        dept.setDeptName("儿科");
        when(deptService.getById(3L)).thenReturn(dept);
        DelegatedToolContext.set(new DelegatedToolPrincipal(7L, 11L, "patient",
                Set.of("departments:read"), "token-1"));

        Dept found = controller.getDepartment(3L).getData();

        assertEquals("儿科", found.getDeptName());
        verify(deptService).getById(3L);
    }

    @Test
    void departmentsToolRejectsMissingScope() {
        DelegatedToolContext.set(new DelegatedToolPrincipal(7L, 11L, "patient", Set.of(), "token-1"));

        assertThrows(BusinessException.class, () -> controller.listDepartments(1));
        assertThrows(BusinessException.class, () -> controller.getDepartment(3L));
        verifyNoInteractions(deptService);
    }

    @Test
    void schedulesToolUsesJavaServiceAfterScopeCheck() {
        LocalDate workDate = LocalDate.of(2026, 9, 2);
        ScheduleVO schedule = new ScheduleVO();
        schedule.setId(9L);
        schedule.setDeptName("内科");
        schedule.setStaffName("张医生");
        when(scheduleService.list(1L, workDate, 8L)).thenReturn(List.of(schedule));
        DelegatedToolContext.set(new DelegatedToolPrincipal(7L, 11L, "patient",
                Set.of("schedules:read"), "token-1"));

        List<ScheduleVO> schedules = controller.listSchedules(1L, workDate, 8L).getData();

        assertEquals("张医生", schedules.getFirst().getStaffName());
        verify(scheduleService).list(1L, workDate, 8L);
    }

    @Test
    void scheduleDetailToolUsesJavaServiceAfterScopeCheck() {
        ScheduleVO schedule = new ScheduleVO();
        schedule.setId(9L);
        schedule.setTimePeriod("上午");
        when(scheduleService.getDetail(9L)).thenReturn(schedule);
        DelegatedToolContext.set(new DelegatedToolPrincipal(7L, 11L, "patient",
                Set.of("schedules:read"), "token-1"));

        ScheduleVO found = controller.getSchedule(9L).getData();

        assertEquals("上午", found.getTimePeriod());
        verify(scheduleService).getDetail(9L);
    }

    @Test
    void schedulesToolRejectsMissingScope() {
        DelegatedToolContext.set(new DelegatedToolPrincipal(7L, 11L, "patient",
                Set.of("departments:read"), "token-1"));

        assertThrows(BusinessException.class, () -> controller.listSchedules(1L, null, null));
        assertThrows(BusinessException.class, () -> controller.getSchedule(9L));
        verifyNoInteractions(scheduleService);
    }

    @Test
    void staffToolUsesJavaServiceAfterScopeCheck() {
        StaffVO staff = new StaffVO();
        staff.setId(8L);
        staff.setName("张医生");
        staff.setTitle("主任医师");
        when(staffService.list(1L, 1)).thenReturn(List.of(staff));
        DelegatedToolContext.set(new DelegatedToolPrincipal(7L, 11L, "patient",
                Set.of("staff:read"), "token-1"));

        List<StaffVO> found = controller.listStaff(1L, 1).getData();

        assertEquals("主任医师", found.getFirst().getTitle());
        verify(staffService).list(1L, 1);
    }

    @Test
    void staffDetailToolUsesJavaServiceAfterScopeCheck() {
        Staff staff = new Staff();
        staff.setId(8L);
        staff.setName("张医生");
        when(staffService.getById(8L)).thenReturn(staff);
        DelegatedToolContext.set(new DelegatedToolPrincipal(7L, 11L, "patient",
                Set.of("staff:read"), "token-1"));

        assertEquals("张医生", controller.getStaff(8L).getData().getName());
        verify(staffService).getById(8L);
    }

    @Test
    void staffToolRejectsMissingScope() {
        DelegatedToolContext.set(new DelegatedToolPrincipal(7L, 11L, "patient",
                Set.of("departments:read"), "token-1"));

        assertThrows(BusinessException.class, () -> controller.listStaff(1L, 1));
        assertThrows(BusinessException.class, () -> controller.getStaff(8L));
        verifyNoInteractions(staffService);
    }

    @Test
    void registrationsToolAlwaysScopesToTokenPatientId() {
        RegistrationVO registration = new RegistrationVO();
        registration.setId(5L);
        registration.setRegNo("R-2026-0001");
        registration.setDeptName("内科");
        when(registrationService.list(11L, null, null, BizStatus.REG_REGISTERED))
                .thenReturn(List.of(registration));
        DelegatedToolContext.set(new DelegatedToolPrincipal(7L, 11L, "patient",
                Set.of("registrations:read"), "token-1"));

        List<RegistrationVO> found = controller.listMyRegistrations(BizStatus.REG_REGISTERED).getData();

        assertEquals("R-2026-0001", found.getFirst().getRegNo());
        verify(registrationService).list(11L, null, null, BizStatus.REG_REGISTERED);
    }

    @Test
    void pendingRegistrationsToolFiltersByRegisteredStatus() {
        when(registrationService.list(11L, null, null, BizStatus.REG_REGISTERED))
                .thenReturn(List.of());
        DelegatedToolContext.set(new DelegatedToolPrincipal(7L, 11L, "patient",
                Set.of("registrations:read"), "token-1"));

        controller.listMyPendingRegistrations();

        verify(registrationService).list(11L, null, null, BizStatus.REG_REGISTERED);
    }

    @Test
    void registrationsToolRejectsTokenWithoutPatientProfile() {
        DelegatedToolContext.set(new DelegatedToolPrincipal(7L, null, "patient",
                Set.of("registrations:read"), "token-1"));

        assertThrows(BusinessException.class, () -> controller.listMyRegistrations(null));
        assertThrows(BusinessException.class, controller::listMyPendingRegistrations);
        verifyNoInteractions(registrationService);
    }

    @Test
    void registrationsToolRejectsMissingScope() {
        DelegatedToolContext.set(new DelegatedToolPrincipal(7L, 11L, "patient",
                Set.of("departments:read"), "token-1"));

        assertThrows(BusinessException.class, () -> controller.listMyRegistrations(null));
        assertThrows(BusinessException.class, controller::listMyPendingRegistrations);
        verifyNoInteractions(registrationService);
    }

    private AiRegistrationCreateRequest createRequest() {
        AiRegistrationCreateRequest body = new AiRegistrationCreateRequest();
        body.setScheduleId(9L);
        body.setIdempotencyKey("conversation-1:call-1");
        return body;
    }

    private void givenWritablePatientToken() {
        DelegatedToolContext.set(new DelegatedToolPrincipal(7L, 11L, AccountType.PATIENT,
                Set.of("registrations:write"), "token-1"));
    }

    @Test
    void createRegistrationForcesTokenPatientIdAndForwardsIdempotencyKey() {
        givenWritablePatientToken();
        when(registrationService.register(any())).thenReturn(55L);
        ArgumentCaptor<RegistrationCreateDTO> sent = ArgumentCaptor.forClass(RegistrationCreateDTO.class);

        assertEquals(55L, controller.createMyRegistration(createRequest()).getData());

        verify(registrationService).register(sent.capture());
        assertEquals(11L, sent.getValue().getPatientId());
        assertEquals(9L, sent.getValue().getScheduleId());
        assertEquals("conversation-1:call-1", sent.getValue().getIdempotencyKey());
    }

    @Test
    void cancelRegistrationDelegatesToBusinessService() {
        givenWritablePatientToken();

        controller.cancelMyRegistration(55L);

        verify(registrationService).cancel(55L);
    }

    @Test
    void writeEndpointsRejectReadOnlyToken() {
        DelegatedToolContext.set(new DelegatedToolPrincipal(7L, 11L, AccountType.PATIENT,
                Set.of("registrations:read"), "token-1"));

        assertThrows(BusinessException.class, () -> controller.createMyRegistration(createRequest()));
        assertThrows(BusinessException.class, () -> controller.cancelMyRegistration(55L));
        verifyNoInteractions(registrationService);
    }

    @Test
    void writeEndpointsRejectNonPatientAccount() {
        DelegatedToolContext.set(new DelegatedToolPrincipal(7L, 11L, AccountType.STAFF,
                Set.of("registrations:write"), "token-1"));

        assertThrows(BusinessException.class, () -> controller.createMyRegistration(createRequest()));
        assertThrows(BusinessException.class, () -> controller.cancelMyRegistration(55L));
        verifyNoInteractions(registrationService);
    }

    @Test
    void writeEndpointsRejectTokenWithoutPatientProfile() {
        DelegatedToolContext.set(new DelegatedToolPrincipal(7L, null, AccountType.PATIENT,
                Set.of("registrations:write"), "token-1"));

        assertThrows(BusinessException.class, () -> controller.createMyRegistration(createRequest()));
        assertThrows(BusinessException.class, () -> controller.cancelMyRegistration(55L));
        verifyNoInteractions(registrationService);
    }

    @Test
    void readEndpointsStillWorkWithoutWriteScope() {
        when(registrationService.list(11L, null, null, null)).thenReturn(List.of());
        DelegatedToolContext.set(new DelegatedToolPrincipal(7L, 11L, AccountType.PATIENT,
                Set.of("registrations:read"), "token-1"));

        controller.listMyRegistrations(null);

        verify(registrationService).list(11L, null, null, null);
    }

    @Test
    void memoryCreateResolvesSourceMessageInsideDelegatedUserScope() {
        DelegatedToolContext.set(new DelegatedToolPrincipal(7L, 11L, AccountType.PATIENT,
                Set.of("memories:write"), "token-1"));
        ChatMessage userMessage = new ChatMessage();
        userMessage.setId(42L);
        userMessage.setRole("user");
        when(chatMessageRepository.selectRecentByConversationIdAndUserId(
                "conversation-1", 7L, 10)).thenReturn(List.of(userMessage));
        AiMemoryWriteRequest body = new AiMemoryWriteRequest();
        body.setType("communication_preference");
        body.setContent("请用简短中文");
        body.setSourceConversationId("conversation-1");
        body.setSourceMessageId(999L);

        controller.createMyMemory(body);

        assertEquals(42L, body.getSourceMessageId());
        verify(chatMessageRepository).selectRecentByConversationIdAndUserId(
                "conversation-1", 7L, 10);
        verify(memoryService).createConfirmed(11L, body);
    }

    @Test
    void clinicalContextUsesDelegatedPatientAndScope() {
        PatientClinicalContextVO context = new PatientClinicalContextVO();
        when(clinicalContextService.load(11L, "demographics,blood_pressure")).thenReturn(context);
        DelegatedToolContext.set(new DelegatedToolPrincipal(7L, 11L, AccountType.PATIENT,
                Set.of("clinical:read"), "token-1"));

        PatientClinicalContextVO loaded = controller.patientClinicalContext("demographics,blood_pressure").getData();

        assertEquals(context, loaded);
        verify(clinicalContextService).load(11L, "demographics,blood_pressure");
    }

    @Test
    void clinicalContextRejectsMissingScope() {
        DelegatedToolContext.set(new DelegatedToolPrincipal(7L, 11L, AccountType.PATIENT,
                Set.of("departments:read"), "token-1"));

        assertThrows(BusinessException.class, () -> controller.patientClinicalContext("allergies"));
        verifyNoInteractions(clinicalContextService);
    }
}
