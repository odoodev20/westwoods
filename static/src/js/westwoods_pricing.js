/** @odoo-module **/

import { WebsiteSale } from "@website_sale/interactions/website_sale";
import { patch } from "@web/core/utils/patch";
import publicWidget from "@web/legacy/js/public/public_widget";

/**
 * Refresh the #westwoods_pricing_box from combination_info (variant / price change).
 */
export function updateWestwoodsPricingBox(combinationInfo, parent) {
    const box = document.getElementById("westwoods_pricing_box");
    if (!box || !combinationInfo) {
        return;
    }

    if (!combinationInfo.westwoods_flow) {
        box.classList.add("d-none");
        return;
    }
    box.classList.remove("d-none");

    const factor = parseFloat(combinationInfo.westwoods_factor) || 1;
    const unitPrice = parseFloat(combinationInfo.price) || 0;
    const unitLabel = combinationInfo.westwoods_unit_label || box.dataset.unitLabel || "";
    const techUnit = combinationInfo.westwoods_tech_unit || box.dataset.techUnit || "";
    const factorLabel = combinationInfo.westwoods_factor_label || "";

    box.dataset.factor = String(factor);
    box.dataset.unitPrice = String(unitPrice);
    box.dataset.unitLabel = unitLabel;
    box.dataset.techUnit = techUnit;
    box.dataset.flow = combinationInfo.westwoods_flow;

    const qtyInput =
        (parent && parent.querySelector && parent.querySelector('input[name="add_qty"]')) ||
        document.querySelector('#product_detail input[name="add_qty"]') ||
        document.querySelector('input[name="add_qty"]');
    const physical = parseFloat(qtyInput && qtyInput.value) || 1;
    const technical = physical * factor;
    const total = technical * unitPrice;

    const setText = (sel, text) => {
        const el = box.querySelector(sel);
        if (el) {
            el.textContent = text;
        }
    };

    setText(
        "#ww_calc_physical",
        Number.isInteger(physical) ? String(physical) : physical.toFixed(2)
    );
    setText("#ww_calc_technical", technical.toFixed(2));
    setText("#ww_display_factor", factor.toFixed(2));
    if (factorLabel) {
        setText("#ww_display_factor_label", factorLabel);
    }
    box.querySelectorAll(".ww_unit_label").forEach((el) => {
        el.textContent = unitLabel;
    });
    box.querySelectorAll(".ww_tech_unit").forEach((el) => {
        el.textContent = techUnit;
    });

    const currencySymbol = box.dataset.currencySymbol || "";
    const formatMoney = (amount) => {
        const formatted = Number(amount).toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
        return `${currencySymbol} ${formatted}`.trim();
    };
    setText("#ww_display_unit_price", formatMoney(unitPrice));
    setText("#ww_calc_total", formatMoney(total));

    // Keep main price suffix in sync (e.g. / m²)
    const mainUnit = document.getElementById("ww_main_price_unit");
    if (mainUnit && techUnit) {
        mainUnit.textContent = "/ " + techUnit;
    }
}

/**
 * Patch the Odoo 19 WebsiteSale interaction so every variant change
 * updates the WestWoods pricing box (factor + unit price + total).
 */
patch(WebsiteSale.prototype, {
    _onChangeCombination(ev, parent, combination) {
        super._onChangeCombination(ev, parent, combination);
        try {
            updateWestwoodsPricingBox(combination, parent);
        } catch (e) {
            console.warn("WestWoods: pricing box update failed", e);
        }
    },
});

/**
 * Qty +/- on product page (does not always go through combination RPC).
 */
publicWidget.registry.WestWoodsPricingBox = publicWidget.Widget.extend({
    selector: "#westwoods_pricing_box",

    start() {
        this._super(...arguments);
        const root = this.el.closest("#product_detail") || document;
        this.qtyInput = root.querySelector('input[name="add_qty"], input.quantity');
        if (this.qtyInput) {
            const refresh = () => {
                updateWestwoodsPricingBox(
                    {
                        westwoods_flow: this.el.dataset.flow || true,
                        westwoods_factor: this.el.dataset.factor,
                        westwoods_unit_label: this.el.dataset.unitLabel,
                        westwoods_tech_unit: this.el.dataset.techUnit,
                        westwoods_factor_label:
                            this.el.querySelector("#ww_display_factor_label")?.textContent,
                        price: this.el.dataset.unitPrice,
                    },
                    this.el.closest(".js_product") || document
                );
            };
            this.qtyInput.addEventListener("change", refresh);
            this.qtyInput.addEventListener("input", refresh);
            root.querySelectorAll(
                ".js_add_cart_json, .css_quantity_minus, .css_quantity_plus"
            ).forEach((btn) => {
                btn.addEventListener("click", () => setTimeout(refresh, 50));
            });
        }
    },
});
