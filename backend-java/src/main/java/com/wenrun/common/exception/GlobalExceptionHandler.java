package com.wenrun.common.exception;

import com.wenrun.common.Result;
import com.wenrun.common.ResultCode;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.ConstraintViolation;
import jakarta.validation.ConstraintViolationException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.validation.BindException;
import org.springframework.web.HttpMediaTypeNotSupportedException;
import org.springframework.web.HttpRequestMethodNotSupportedException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.MissingServletRequestParameterException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;
import org.springframework.web.multipart.MaxUploadSizeExceededException;
import org.springframework.web.servlet.resource.NoResourceFoundException;

import java.util.stream.Collectors;

/**
 * 全局异常处理
 */
@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

    // ==================== 业务异常 ====================

    @ExceptionHandler(BusinessException.class)
    public Result<Void> handleBusinessException(BusinessException ex) {
        log.warn("业务异常: {}", ex.getMessage());
        return Result.fail(ex.getCode(), ex.getMessage());
    }

    // ==================== 参数校验异常 ====================

    /**
     * @RequestBody @Valid 校验失败
     */
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public Result<Void> handleMethodArgumentNotValid(MethodArgumentNotValidException ex) {
        String msg = ex.getBindingResult().getFieldErrors().stream()
                .map(e -> e.getField() + ": " + e.getDefaultMessage())
                .collect(Collectors.joining("; "));
        log.warn("参数校验失败: {}", msg);
        return Result.fail(ResultCode.BAD_REQUEST, msg);
    }

    /**
     * @ModelAttribute / 表单绑定校验失败
     */
    @ExceptionHandler(BindException.class)
    public Result<Void> handleBindException(BindException ex) {
        String msg = ex.getBindingResult().getFieldErrors().stream()
                .map(e -> e.getField() + ": " + e.getDefaultMessage())
                .collect(Collectors.joining("; "));
        log.warn("参数绑定失败: {}", msg);
        return Result.fail(ResultCode.BAD_REQUEST, msg);
    }

    /**
     * @RequestParam / @PathVariable 上 @Validated 校验失败
     */
    @ExceptionHandler(ConstraintViolationException.class)
    public Result<Void> handleConstraintViolation(ConstraintViolationException ex) {
        String msg = ex.getConstraintViolations().stream()
                .map(ConstraintViolation::getMessage)
                .collect(Collectors.joining("; "));
        log.warn("参数约束校验失败: {}", msg);
        return Result.fail(ResultCode.BAD_REQUEST, msg);
    }

    /**
     * 缺少必需的请求参数
     */
    @ExceptionHandler(MissingServletRequestParameterException.class)
    public Result<Void> handleMissingServletRequestParameter(MissingServletRequestParameterException ex) {
        String msg = "缺少必需参数: " + ex.getParameterName();
        log.warn(msg);
        return Result.fail(ResultCode.BAD_REQUEST, msg);
    }

    /**
     * 方法参数类型转换失败 (如 @RequestParam Integer 传入了 "abc")
     */
    @ExceptionHandler(MethodArgumentTypeMismatchException.class)
    public Result<Void> handleMethodArgumentTypeMismatch(MethodArgumentTypeMismatchException ex) {
        String msg = String.format("参数 '%s' 类型错误，期望 %s，实际值: %s",
                ex.getName(),
                ex.getRequiredType() != null ? ex.getRequiredType().getSimpleName() : "未知",
                ex.getValue());
        log.warn(msg);
        return Result.fail(ResultCode.BAD_REQUEST, msg);
    }

    /**
     * 请求体格式错误 / JSON 解析失败
     */
    @ExceptionHandler(HttpMessageNotReadableException.class)
    public Result<Void> handleHttpMessageNotReadable(HttpMessageNotReadableException ex) {
        log.warn("请求体解析失败: {}", ex.getMessage());
        return Result.fail(ResultCode.BAD_REQUEST, "请求体格式错误，请检查 JSON 格式");
    }

    // ==================== 请求/路由异常 ====================

    /**
     * 请求方法不支持 (如 GET 访问 POST 接口)
     */
    @ExceptionHandler(HttpRequestMethodNotSupportedException.class)
    public Result<Void> handleHttpRequestMethodNotSupported(HttpRequestMethodNotSupportedException ex) {
        String msg = "不支持的请求方法: " + ex.getMethod();
        log.warn(msg);
        return Result.fail(ResultCode.BAD_REQUEST, msg);
    }

    /**
     * Content-Type 不支持
     */
    @ExceptionHandler(HttpMediaTypeNotSupportedException.class)
    public Result<Void> handleHttpMediaTypeNotSupported(HttpMediaTypeNotSupportedException ex) {
        log.warn("不支持的 Content-Type: {}", ex.getContentType());
        return Result.fail(ResultCode.BAD_REQUEST, "不支持的 Content-Type");
    }

    /**
     * 资源不存在 (Spring Boot 3 / Spring MVC 6 的 404)
     */
    @ExceptionHandler(NoResourceFoundException.class)
    public Result<Void> handleNoResourceFound(NoResourceFoundException ex, HttpServletRequest request) {
        log.warn("资源不存在: {} {}", request.getMethod(), request.getRequestURI());
        return Result.fail(ResultCode.NOT_FOUND, "请求的资源不存在");
    }

    // ==================== 文件上传异常 ====================

    /**
     * 上传文件超过限制大小
     */
    @ExceptionHandler(MaxUploadSizeExceededException.class)
    public Result<Void> handleMaxUploadSizeExceeded(MaxUploadSizeExceededException ex) {
        log.warn("上传文件超过大小限制: {}", ex.getMessage());
        return Result.fail(ResultCode.BAD_REQUEST, "上传文件大小超过限制");
    }

    // ==================== 兜底异常 ====================

    @ExceptionHandler(Exception.class)
    public Result<Void> handleException(Exception ex, HttpServletRequest request) {
        log.error("系统异常 [{} {}]: {}",
                request.getMethod(), request.getRequestURI(), ex.getMessage(), ex);
        return Result.fail(ResultCode.INTERNAL_ERROR, "系统繁忙，请稍后重试");
    }
}
