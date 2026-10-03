/** @odoo-module **/

import { WebsiteSale } from "@website_sale/interactions/website_sale";
import { patch } from "@web/core/utils/patch";

/**
 * Highlight matrix row matching current combination product_id.
 */
function highlightMatrixRow(productId) {
    const matrix = document.getElementById("westwoods_variant_matrix");
    if (!matrix) {
        return;
    }
    matrix.querySelectorAll("tr.o_ww_matrix_row").forEach((row) => {
        const id = parseInt(row.dataset.productId, 10);
        if (productId && id === productId) {
            row.classList.add("table-primary");
        } else {
            row.classList.remove("table-primary");
        }
    });
}

/**
 * Click matrix row → select matching attribute values in standard Odoo selector.
 */
function bindMatrixRowClicks() {
    const matrix = document.getElementById("westwoods_variant_matrix");
    if (!matrix || matrix.dataset.wwBound) {
        return;
    }
    matrix.dataset.wwBound = "1";
    matrix.querySelectorAll("tr.o_ww_matrix_row").forEach((row) => {
        row.addEventListener("click", () => {
            const ptavIds = (row.dataset.ptavIds || "")
                .split(",")
                .map((x) => parseInt(x, 10))
                .filter(Boolean);
            if (!ptavIds.length) {
                return;
            }
            const root =
                document.querySelector(".js_main_product") ||
                document.querySelector(".js_product") ||
                document;
            ptavIds.forEach((ptavId) => {
                // Radio / pill inputs
                const input = root.querySelector(
                    `input[type="radio"][value="${ptavId}"], input.js_variant_change[value="${ptavId}"]`
                );
                if (input && !input.checked) {
                    input.checked = true;
                    input.dispatchEvent(new Event("change", { bubbles: true }));
                    return;
                }
                // Select options
                const option = root.querySelector(`select option[value="${ptavId}"]`);
                if (option && option.parentElement) {
                    option.parentElement.value = String(ptavId);
                    option.parentElement.dispatchEvent(new Event("change", { bubbles: true }));
                }
            });
            highlightMatrixRow(parseInt(row.dataset.productId, 10));
        });
    });
}

// Highlight after combination changes
patch(WebsiteSale.prototype, {
    _onChangeCombination(ev, parent, combination) {
        super._onChangeCombination(ev, parent, combination);
        try {
            const productId = combination && combination.product_id;
            highlightMatrixRow(productId);
        } catch (e) {
            console.warn("WestWoods matrix highlight failed", e);
        }
    },
    start() {
        const res = super.start(...arguments);
        try {
            bindMatrixRowClicks();
        } catch (e) {
            console.warn("WestWoods matrix bind failed", e);
        }
        return res;
    },
});

// Bind on DOM ready if interaction already started
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bindMatrixRowClicks);
} else {
    bindMatrixRowClicks();
}
