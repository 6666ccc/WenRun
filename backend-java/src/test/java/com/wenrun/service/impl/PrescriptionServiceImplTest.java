package com.wenrun.service.impl;

import com.wenrun.common.constant.BizStatus;
import com.wenrun.common.exception.BusinessException;
import com.wenrun.entity.OutpatientVisit;
import com.wenrun.entity.Prescription;
import com.wenrun.repository.DrugRepository;
import com.wenrun.repository.OutpatientVisitRepository;
import com.wenrun.repository.PatientRepository;
import com.wenrun.repository.PrescriptionItemRepository;
import com.wenrun.repository.PrescriptionRepository;
import com.wenrun.service.support.CurrentStaffSupport;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class PrescriptionServiceImplTest {

    private final PrescriptionRepository prescriptionMapper = mock(PrescriptionRepository.class);
    private final OutpatientVisitRepository visitMapper = mock(OutpatientVisitRepository.class);
    private final CurrentStaffSupport currentStaffSupport = mock(CurrentStaffSupport.class);
    private final PrescriptionServiceImpl service = new PrescriptionServiceImpl(prescriptionMapper,
            mock(PrescriptionItemRepository.class), visitMapper, mock(DrugRepository.class), mock(PatientRepository.class), currentStaffSupport);

    @Test
    void staffCannotCancelPrescriptionForAnotherDoctorsVisit() {
        Prescription prescription = new Prescription();
        prescription.setId(7L);
        prescription.setVisitId(3L);
        prescription.setStatus(BizStatus.RX_PENDING_PAY);
        OutpatientVisit visit = new OutpatientVisit();
        visit.setId(3L);
        visit.setStaffId(22L);
        BusinessException denied = new BusinessException("Access denied");

        when(prescriptionMapper.selectById(7L)).thenReturn(prescription);
        when(visitMapper.selectById(3L)).thenReturn(visit);
        doThrow(denied).when(currentStaffSupport).assertOwnsStaff(22L);

        assertThrows(BusinessException.class, () -> service.cancel(7L));

        verify(prescriptionMapper, never()).updateStatus(7L, BizStatus.RX_CANCELLED);
    }
}
