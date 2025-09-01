using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.Rendering;
using Microsoft.EntityFrameworkCore;
using FinserveNew.Data;
using FinserveNew.Models;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Identity;
using Microsoft.AspNetCore.Identity.UI.Services;

namespace FinserveNew.Controllers
{
    [Route("[controller]")]
    public class LeavesController : Controller
    {
        private readonly AppDbContext _context;
        private readonly ILogger<LeavesController> _logger;
        private readonly UserManager<ApplicationUser> _userManager;
        private readonly IEmailSender _emailSender;

        public LeavesController(AppDbContext context, ILogger<LeavesController> logger, UserManager<ApplicationUser> userManager, IEmailSender emailSender)
        {
            _context = context;
            _logger = logger;
            _userManager = userManager;
            _emailSender = emailSender;
        }

        // ================== HELPER METHOD TO GET EMPLOYEE ID ==================
        private async Task<string> GetCurrentEmployeeId()
        {
            var currentUser = await _userManager.GetUserAsync(User);

            if (currentUser == null)
            {
                _logger.LogWarning("No authenticated user found");
                return null;
            }

            _logger.LogInformation($"Current user: {currentUser.UserName}, Email: {currentUser.Email}");

            var employee = await _context.Employees
                .FirstOrDefaultAsync(e => e.Username == currentUser.UserName || e.Email == currentUser.Email);

            if (employee == null)
            {
                _logger.LogWarning($"No employee found for username: {currentUser.UserName} or email: {currentUser.Email}");
            }

            return employee?.EmployeeID;
        }

        // ================== EMPLOYEE ACTIONS ==================

        [Authorize(Roles = "Employee")]
        [HttpGet("LeaveRecords")]
        public async Task<IActionResult> LeaveRecords()
        {
            var employeeId = await GetCurrentEmployeeId();

            if (string.IsNullOrEmpty(employeeId))
            {
                TempData["Error"] = "Employee record not found.";
                return View("~/Views/Employee/Leaves/LeaveRecords.cshtml", new List<LeaveModel>());
            }

            var leaves = await _context.Leaves
                .Include(l => l.Employee)
                .Include(l => l.LeaveType)
                .Where(l => l.EmployeeID == employeeId)
                .OrderByDescending(l => l.SubmissionDate != DateTime.MinValue ? l.SubmissionDate : l.CreatedDate)
                .ThenByDescending(l => l.LeaveID)
                .ToListAsync();

            var leaveBalances = await CalculateLeaveBalancesAsync(employeeId);
            ViewBag.LeaveBalances = leaveBalances;
            PopulateLeaveBalanceViewBag(leaveBalances);

            // Check for unpaid leave requests (pending or approved)
            var unpaidLeaveRequests = await _context.UnpaidLeaveRequests
                .Where(u => u.EmployeeID == employeeId &&
                           (u.Status == "Pending" || u.Status == "Approved"))
                .ToListAsync();

            ViewBag.HasUnpaidLeaveRequests = unpaidLeaveRequests.Any();
            ViewBag.UnpaidLeaveRequestCount = unpaidLeaveRequests.Count;

            return View("~/Views/Employee/Leaves/LeaveRecords.cshtml", leaves);
        }

        [Authorize(Roles = "Employee")]
        [HttpGet("Details/{id:int}")]
        public async Task<IActionResult> Details(int? id)
        {
            if (id == null)
            {
                return NotFound();
            }

            var employeeId = await GetCurrentEmployeeId();
            if (string.IsNullOrEmpty(employeeId))
            {
                return NotFound();
            }

            var leave = await _context.Leaves
                .Include(l => l.Employee)
                .Include(l => l.LeaveType)
                .FirstOrDefaultAsync(m => m.LeaveID == id && m.EmployeeID == employeeId);

            if (leave == null)
            {
                return NotFound();
            }

            var leaveDetails = await _context.LeaveDetails
                .FirstOrDefaultAsync(ld => ld.LeaveID == id);

            if (leaveDetails != null)
            {
                ViewBag.HasMedicalCertificate = true;
                ViewBag.MedicalCertificateFileName = Path.GetFileName(leaveDetails.DocumentPath);
                ViewBag.MedicalCertificateUrl = leaveDetails.DocumentPath;
                ViewBag.MedicalCertificateUploadDate = leaveDetails.UploadDate.ToString("dd/MM/yyyy HH:mm") ?? "Unknown";
            }
            else
            {
                ViewBag.HasMedicalCertificate = false;
                ViewBag.MedicalCertificateFileName = "";
                ViewBag.MedicalCertificateUrl = "";
                ViewBag.MedicalCertificateUploadDate = "";
            }

            return View("~/Views/Employee/Leaves/Details.cshtml", leave);
        }

        [Authorize(Roles = "Employee")]
        [HttpGet("Create")]
        public async Task<IActionResult> Create()
        {
            _logger.LogInformation("📋 Loading Create Leave form");

            await PopulateLeaveTypeDropdownAsync();

            var employeeId = await GetCurrentEmployeeId();
            if (string.IsNullOrEmpty(employeeId))
            {
                TempData["Error"] = "Employee record not found.";
                return View("~/Views/Employee/Leaves/Create.cshtml");
            }

            var leaveBalances = await CalculateLeaveBalancesAsync(employeeId);
            ViewBag.LeaveBalances = leaveBalances;
            PopulateLeaveBalanceViewBag(leaveBalances);

            _logger.LogInformation("✅ Create Leave form loaded successfully");
            return View("~/Views/Employee/Leaves/Create.cshtml");
        }

        [HttpPost("Create")]
        [ValidateAntiForgeryToken]
        [Authorize(Roles = "Employee")]
        public async Task<IActionResult> Create(LeaveModel leave, IFormFile? MedicalCertificate, string DayType = "full",
      string? JustificationReason = null, bool ConfirmUnpaidLeave = false,
      string? AlternativeLeaveChoice = null, string? AlternativeLeaveTypeIds = null)
        {
            // ... existing Create POST logic remains the same ...
            // (I'm not including the full method to keep this response manageable)
            
            _logger.LogInformation("🚀 CREATE LEAVE POST started");
            // ... rest of the existing method
            return View("~/Views/Employee/Leaves/Create.cshtml", leave);
        }

        [Authorize(Roles = "Employee")]
        [HttpGet("Edit/{id:int}")]
        public async Task<IActionResult> Edit(int? id)
        {
            if (id == null)
            {
                return NotFound();
            }

            var employeeId = await GetCurrentEmployeeId();
            if (string.IsNullOrEmpty(employeeId))
            {
                return NotFound();
            }

            var leave = await _context.Leaves
                .Include(l => l.Employee)
                .Include(l => l.LeaveType)
                .FirstOrDefaultAsync(m => m.LeaveID == id && m.EmployeeID == employeeId);

            if (leave == null)
            {
                return NotFound();
            }

            // Only allow editing if status is Pending
            if (leave.Status != "Pending")
            {
                TempData["Error"] = "You can only edit leaves that are in Pending status.";
                return RedirectToAction(nameof(LeaveRecords));
            }

            // Check if this is an Emergency Leave
            if (leave.LeaveType.TypeName.ToLower().Contains("annual") &&
                !string.IsNullOrEmpty(leave.Reason) &&
                leave.Reason.Contains("[EMERGENCY LEAVE]"))
            {
                leave.LeaveTypeID = 4; // Display as Emergency Leave
                leave.Reason = leave.Reason.Replace("[EMERGENCY LEAVE]", "").Trim();
            }

            await PopulateLeaveTypeDropdownAsync();
            var leaveBalances = await CalculateLeaveBalancesAsync(employeeId);
            ViewBag.LeaveBalances = leaveBalances;
            PopulateLeaveBalanceViewBag(leaveBalances);

            var leaveDetails = await _context.LeaveDetails
                .FirstOrDefaultAsync(ld => ld.LeaveID == id);

            if (leaveDetails != null)
            {
                ViewBag.HasMedicalCertificate = true;
                ViewBag.MedicalCertificateFileName = Path.GetFileName(leaveDetails.DocumentPath);
                ViewBag.MedicalCertificateUrl = leaveDetails.DocumentPath;
            }
            else
            {
                ViewBag.HasMedicalCertificate = false;
                ViewBag.MedicalCertificateFileName = "";
                ViewBag.MedicalCertificateUrl = "";
            }

            return View("~/Views/Employee/Leaves/Edit.cshtml", leave);
        }

        [HttpPost("Edit/{id:int}")]
        [ValidateAntiForgeryToken]
        [Authorize(Roles = "Employee")]
        public async Task<IActionResult> Edit(int id, LeaveModel leave, IFormFile? MedicalCertificate, string DayType = "full",
    string? AlternativeLeaveChoice = null, string? AlternativeLeaveTypeIds = null, string? JustificationReason = null)
        {
            // ... existing Edit POST logic remains the same ...
            // (I'm not including the full method to keep this response manageable)
            
            if (id != leave.LeaveID)
                return NotFound();

            // ... rest of the existing method
            return View("~/Views/Employee/Leaves/Edit.cshtml", leave);
        }

        // ... rest of the controller methods remain the same ...

        // ================== HELPER METHODS ==================
        // (All helper methods remain unchanged)
        
        private async Task<Dictionary<string, object>> CalculateLeaveBalancesAsync(string employeeId, int year = 0)
        {
            // ... existing implementation
            return new Dictionary<string, object>();
        }

        private async Task PopulateLeaveTypeDropdownAsync()
        {
            // ... existing implementation
        }

        // ... all other helper methods remain the same ...
    }
}