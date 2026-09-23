package com.wenrun.repository;

import com.wenrun.ai.vo.PatientDocumentCatalogItem;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

@Mapper
public interface PatientMedicalDocumentRepository {

    List<PatientDocumentCatalogItem> selectCatalog(@Param("patientId") Long patientId,
                                                    @Param("limit") int limit);
}
