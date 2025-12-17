package com.devpulse.backend.config;

import com.devpulse.backend.metrics.MetricsService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Configuration;
import org.springframework.lang.NonNull;
import org.springframework.web.servlet.HandlerInterceptor;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@Configuration
@RequiredArgsConstructor
public class MetricsConfig implements WebMvcConfigurer {

    private final MetricsService metricsService;

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(new HandlerInterceptor() {
            @Override
            public boolean preHandle(@NonNull HttpServletRequest request,
                                      @NonNull HttpServletResponse response,
                                      @NonNull Object handler) {
                request.setAttribute("_metricsStartMs", System.currentTimeMillis());
                return true;
            }

            @Override
            public void afterCompletion(@NonNull HttpServletRequest request,
                                         @NonNull HttpServletResponse response,
                                         @NonNull Object handler, Exception ex) {
                Long startMs = (Long) request.getAttribute("_metricsStartMs");
                if (startMs != null) {
                    long duration = System.currentTimeMillis() - startMs;
                    metricsService.recordRequest(request.getMethod(),
                        request.getRequestURI(), response.getStatus());
                    metricsService.recordLatency(request.getRequestURI(), duration);
                }
            }
        });
    }
}
