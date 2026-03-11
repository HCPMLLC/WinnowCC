/**
 * Winnow Career Page Widget
 * Embed jobs from Winnow on any website
 *
 * Usage:
 * <div id="winnow-jobs" data-slug="your-slug"></div>
 * <script src="https://api.winnowcc.ai/embed/winnow-widget.js" async></script>
 */
(function () {
  "use strict";

  var API_BASE = "https://api.winnowcc.ai/api/public/career-pages";

  function init() {
    var containers = document.querySelectorAll(
      '[id="winnow-jobs"], [data-winnow]'
    );
    containers.forEach(renderWidget);
  }

  function renderWidget(container) {
    var slug = container.dataset.slug || container.dataset.winnow;
    if (!slug) {
      console.error("Winnow Widget: Missing data-slug attribute");
      return;
    }

    var apiKey = container.dataset.apiKey || (window.WinnowConfig && window.WinnowConfig.apiKey);

    // Show loading
    container.innerHTML =
      '<div style="text-align:center;padding:40px;color:#666;">Loading jobs...</div>';

    var headers = { "Content-Type": "application/json" };
    if (apiKey) headers["X-API-Key"] = apiKey;

    // Fetch config
    fetch(API_BASE + "/" + slug, { headers: headers })
      .then(function (res) {
        if (!res.ok) throw new Error("Page not found");
        return res.json();
      })
      .then(function (config) {
        // Fetch jobs
        return fetch(API_BASE + "/" + slug + "/jobs?page_size=20", {
          headers: headers,
        })
          .then(function (res) {
            return res.json();
          })
          .then(function (jobsData) {
            container.innerHTML = renderJobList(config, jobsData);
            attachListeners(container, slug);
          });
      })
      .catch(function (err) {
        console.error("Winnow Widget Error:", err);
        container.innerHTML =
          '<div style="text-align:center;padding:40px;color:#999;">Unable to load jobs</div>';
      });
  }

  function renderJobList(config, jobsData) {
    var colors = (config.config && config.config.branding && config.config.branding.colors) || {};
    var primary = colors.primary || "#1B3025";
    var layoutConfig = (config.config && config.config.layout) || {};
    var showIPS = layoutConfig.show_ips_preview !== false;
    var showSalary = layoutConfig.show_salary_ranges !== false;

    var jobsHtml = jobsData.jobs
      .map(function (job) {
        var salaryHtml = "";
        if (showSalary && job.salary_min) {
          salaryHtml =
            '<div style="font-size:13px;color:#888;">$' +
            job.salary_min.toLocaleString() +
            (job.salary_max
              ? " - $" + job.salary_max.toLocaleString()
              : "+") +
            "</div>";
        }
        var ipsHtml = "";
        if (showIPS && job.ips_score) {
          ipsHtml =
            '<span style="display:inline-block;margin-top:8px;padding:2px 8px;background:#dcfce7;color:#166534;font-size:12px;border-radius:4px;">' +
            job.ips_score +
            "% Match</span>";
        }
        var companyHtml = job.company
          ? '<div style="font-size:14px;color:#444;margin-bottom:4px;font-weight:500;">' + escapeHtml(job.company) + "</div>"
          : "";
        var deadlineHtml = job.application_deadline
          ? '<div style="font-size:12px;color:#999;margin-top:4px;">Deadline: ' + new Date(job.application_deadline).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) + "</div>"
          : "";
        return (
          '<div class="winnow-job" style="border:1px solid #e5e7eb;border-radius:8px;padding:16px;margin-bottom:12px;transition:box-shadow 0.2s;" onmouseover="this.style.boxShadow=\'0 4px 12px rgba(0,0,0,0.1)\'" onmouseout="this.style.boxShadow=\'none\'">' +
          '<h3 style="margin:0 0 4px;font-size:16px;font-weight:600;color:#111;">' +
          escapeHtml(job.title) +
          "</h3>" +
          companyHtml +
          '<div style="font-size:14px;color:#666;margin-bottom:4px;">' +
          (job.location
            ? "<span>" + escapeHtml(job.location) + "</span>"
            : "") +
          "</div>" +
          salaryHtml +
          deadlineHtml +
          ipsHtml +
          '<button class="winnow-apply-btn" data-job-id="' +
          job.id +
          '" style="display:block;width:100%;margin-top:12px;padding:10px;background:' +
          primary +
          ";color:white;border:none;border-radius:6px;font-size:14px;font-weight:500;cursor:pointer;" +
          '">Apply Now</button>' +
          "</div>"
        );
      })
      .join("");

    return (
      '<div class="winnow-widget" style="font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;">' +
      '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">' +
      '<span style="font-size:14px;color:#666;">' +
      jobsData.total +
      " open position" +
      (jobsData.total !== 1 ? "s" : "") +
      "</span>" +
      "</div>" +
      '<div class="winnow-jobs-list">' +
      (jobsHtml ||
        '<p style="color:#999;text-align:center;">No open positions</p>') +
      "</div>" +
      '<div style="text-align:center;margin-top:16px;font-size:12px;color:#999;">' +
      'Powered by <a href="https://winnowcc.ai" target="_blank" style="color:' +
      primary +
      ';text-decoration:none;">Winnow</a>' +
      "</div>" +
      "</div>"
    );
  }

  function attachListeners(container, slug) {
    var buttons = container.querySelectorAll(".winnow-apply-btn");
    buttons.forEach(function (btn) {
      btn.addEventListener("click", function () {
        var jobId = btn.dataset.jobId;
        window.open(
          "https://careers.winnowcc.ai/" + slug + "/jobs/" + jobId + "/apply",
          "_blank"
        );
      });
    });
  }

  function escapeHtml(str) {
    if (!str) return "";
    var map = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    };
    return str.replace(/[&<>"']/g, function (c) {
      return map[c];
    });
  }

  // Initialize on DOM ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
