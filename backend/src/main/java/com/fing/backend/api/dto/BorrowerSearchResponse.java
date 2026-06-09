package com.fing.backend.api.dto;

import org.springframework.data.domain.Page;

import java.util.List;

public class BorrowerSearchResponse {

    private List<BorrowerResponse> items;
    private int page;
    private int size;
    private long totalElements;
    private int totalPages;

    public static BorrowerSearchResponse fromPage(Page<BorrowerResponse> pageResult) {
        BorrowerSearchResponse response = new BorrowerSearchResponse();
        response.items = pageResult.getContent();
        response.page = pageResult.getNumber();
        response.size = pageResult.getSize();
        response.totalElements = pageResult.getTotalElements();
        response.totalPages = pageResult.getTotalPages();
        return response;
    }

    public List<BorrowerResponse> getItems() {
        return items;
    }

    public int getPage() {
        return page;
    }

    public int getSize() {
        return size;
    }

    public long getTotalElements() {
        return totalElements;
    }

    public int getTotalPages() {
        return totalPages;
    }
}
