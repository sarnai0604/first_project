using OpenQA.Selenium;
using OpenQA.Selenium.Chrome;
using OpenQA.Selenium.Interactions;
using OpenQA.Selenium.Remote;
using FbAccountWithoutLogin.Libraries;
using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Data;
using System.Data.SqlClient;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Net;
using System.Threading;
using System.Threading.Tasks;
using System.Web;
using System.Windows.Forms;
using System.Data.Common;
using System.Web.UI.WebControls;
using System.Xml.Linq;
using System.Xml;
using System.Text.RegularExpressions;
using FbAccountWithoutLogin.DAL.MainDALTableAdapters;
using static System.Collections.Specialized.BitVector32;
using OpenQA.Selenium.Support.UI;
using Newtonsoft.Json;

namespace FbAccountWithoutLogin
{
    // FbCookieAccount бүтцийг namespace дотор тодорхойлж, давхардлын алдааг (CS0106/CS0229) засав
    public class FbCookieAccount
    {
        public Guid ID { get; set; }
        public string Email { get; set; }
        public string CookieJson { get; set; }
        public int GroupNumber { get; set; }
    }

    struct InsertKeyWord
    {
        public string Keyword;
        public bool IsInsert;
    }
    struct FromUserInfo
    {
        public string FromID;
        public string FromUserName;
        public string FromUrl;
    }

    public partial class FrmMain : Form
    {
        int index;
        int workerIndex;
        int queue_indx = 1;
        List<(Guid, string, string)> queue;
        int priorityHigh = 1;
        int priorityMed  = 1;
        int priorityLow  = 1;
        int session = 0;
        string gridHubUrl;
        GridStatusChecker gridStatusChecker;
        private string PCName;
        string searchURL;
        IWebDriver driver;
        int s    = 0;
        int Part = 0;
        Facebook_AccTableAdapter Facebook_AccTableAdapter;
        DAL.MainDAL.Facebook_AccDataTable Facebook_AccDataTable;

        // ── Cookie rotation fields ───────────────────────────────
        private List<FbCookieAccount> _cookieAccounts = new List<FbCookieAccount>();
        private int _cookieAccountIndex = 0;
        private readonly object _cookieLock = new object();
        private string _connStr = @"Server=10.10.15.202;Database=sumbee;Integrated Security=True;";

        public FrmMain()
        {
            InitializeComponent();
            queue = new List<(Guid, string, string)>();
            Guid ID = Guid.Empty;
            gridHubUrl = "http://10.10.15.249:4444/";
            gridStatusChecker = new GridStatusChecker(gridHubUrl);
        }

        // ════════════════════════════════════════════════════════
        // SQL-С COOKIE ТАТАХ
        // ════════════════════════════════════════════════════════
        private void LoadCookieAccounts()
        {
            _cookieAccounts.Clear();
            try
            {
                using (var conn = new SqlConnection(_connStr))
                {
                    conn.Open();
                    var cmd = new SqlCommand(@"
                        SELECT ID, Email, Cookies, Group_Number
                        FROM [Facebook Users]
                        WHERE isActive         = 1
                          AND isLoginByCookie  = 1
                          AND isExpiredCookies = 0
                          AND isWrongPass      = 0
                          AND IsMobileBlocked  = 0
                          AND Cookies IS NOT NULL
                        ORDER BY BlockedDate ASC", conn);

                    using (var reader = cmd.ExecuteReader())
                    {
                        while (reader.Read())
                        {
                            _cookieAccounts.Add(new FbCookieAccount
                            {
                                ID          = reader.GetGuid(0),
                                Email       = reader.IsDBNull(1) ? "" : reader.GetString(1),
                                CookieJson  = reader.GetString(2),
                                GroupNumber = reader.IsDBNull(3) ? 0 : reader.GetInt32(3)
                            });
                        }
                    }
                }
                Console.WriteLine($"[Cookie] {_cookieAccounts.Count} account ачааллаа.");
            }
            catch (Exception ex)
            {
                Console.WriteLine("[Cookie] LoadCookieAccounts алдаа: " + ex.Message);
            }
        }

        // ════════════════════════════════════════════════════════
        // ROTATION
        // ════════════════════════════════════════════════════════
        private FbCookieAccount GetNextCookieAccount()
        {
            lock (_cookieLock)
            {
                if (_cookieAccounts.Count == 0)
                    LoadCookieAccounts();

                if (_cookieAccounts.Count == 0)
                    throw new Exception("Хүчинтэй cookie бүхий account байхгүй.");

                var account = _cookieAccounts[_cookieAccountIndex % _cookieAccounts.Count];
                _cookieAccountIndex++;
                return account;
            }
        }

        private void MarkCookieExpired(Guid accountId)
        {
            try
            {
                using (var conn = new SqlConnection(_connStr))
                {
                    conn.Open();
                    var cmd = new SqlCommand(@"
                        UPDATE [Facebook Users]
                        SET isExpiredCookies = 1,
                            BlockedDate      = GETDATE()
                        WHERE ID = @id", conn);
                    cmd.Parameters.AddWithValue("@id", accountId);
                    cmd.ExecuteNonQuery();
                }
                lock (_cookieLock)
                {
                    _cookieAccounts.RemoveAll(a => a.ID == accountId);
                }
                Console.WriteLine($"[Cookie] Expired тэмдэглэгдлээ: {accountId}");
            }
            catch (Exception ex)
            {
                Console.WriteLine("[Cookie] MarkExpired алдаа: " + ex.Message);
            }
        }

        // ════════════════════════════════════════════════════════
        // COOKIE INJECT
        // ════════════════════════════════════════════════════════
        private bool InjectCookies(IWebDriver drv, FbCookieAccount account)
        {
            try
            {
                drv.Manage().Cookies.DeleteAllCookies();

                var cookieList = JsonConvert.DeserializeObject<List<Dictionary<string, string>>>(account.CookieJson);
                if (cookieList == null || cookieList.Count == 0)
                {
                    Console.WriteLine($"[Cookie] Cookie хоосон: {account.Email}");
                    return false;
                }

                foreach (var c in cookieList)
                {
                    try
                    {
                        if (!c.ContainsKey("Name") || !c.ContainsKey("Value")) continue;
                        string name  = c["Name"];
                        string value = c["Value"];
                        if (string.IsNullOrEmpty(name) || value == null) continue;

                        drv.Manage().Cookies.AddCookie(
                            new OpenQA.Selenium.Cookie(name, value, ".facebook.com", "/", null));
                    }
                    catch { }
                }

                Console.WriteLine($"[Cookie] {cookieList.Count} cookie inject хийлээ: {account.Email}");
                return true;
            }
            catch (Exception ex)
            {
                Console.WriteLine("[Cookie] InjectCookies алдаа: " + ex.Message);
                return false;
            }
        }

        // ════════════════════════════════════════════════════════
        // LOGIN ШАЛГАХ
        // ════════════════════════════════════════════════════════
        private bool IsLoggedIn(IWebDriver drv)
        {
            try
            {
                string url = drv.Url;
                if (url.Contains("/login") || url.Contains("checkpoint"))
                    return false;

                var cUser = drv.Manage().Cookies.GetCookieNamed("c_user");
                if (cUser != null && !string.IsNullOrEmpty(cUser.Value))
                    return true;

                try
                {
                    drv.FindElement(By.CssSelector(
                        "div[aria-label='Your profile'], a[aria-label='Profile'], div[data-testid='blue_bar_profile_link']"));
                    return true;
                }
                catch { }

                return false;
            }
            catch { return false; }
        }

        // ════════════════════════════════════════════════════════
        // chromeDriver — cookie inject хийж нэвтэрнэ
        // ════════════════════════════════════════════════════════
        private IWebDriver chromeDriver()
        {
            IWebDriver drv = null;
            int retryCount = 0;
            const int MAX_RETRY = 3;

            while (retryCount < MAX_RETRY)
            {
                FbCookieAccount account = null;
                try
                {
                    account = GetNextCookieAccount();

                    ChromeOptions options = new ChromeOptions();
                    options.AddArguments("--no-sandbox");
                    options.AddArguments("--disable-notifications");
                    options.AddArguments("--disable-dev-shm-usage");
                    options.AddArguments("--timezone=Asia/Ulaanbaatar");
                    options.AddArguments("--lang=en-US");
                    options.AddArgument("--start-maximized");
                    options.AddAdditionalOption("useAutomationExtension", false);
                    options.AddArguments("--disable-blink-features=AutomationControlled");
                    options.AddArgument("--disable-extensions");

                    drv = new RemoteWebDriver(
                        new Uri("http://10.10.15.249:4444/wd/hub"),
                        options.ToCapabilities());

                    drv.Navigate().GoToUrl("https://www.facebook.com/");
                    Thread.Sleep(2000);

                    bool injected = InjectCookies(drv, account);
                    if (!injected)
                    {
                        retryCount++;
                        drv.Quit();
                        drv = null;
                        continue;
                    }

                    drv.Navigate().GoToUrl("https://www.facebook.com/");
                    Thread.Sleep(4000);

                    if (IsLoggedIn(drv))
                    {
                        Console.WriteLine($"[Cookie] Нэвтэрлээ: {account.Email}");
                        return drv;
                    }
                    else
                    {
                        Console.WriteLine($"[Cookie] Cookie дууссан: {account.Email}");
                        MarkCookieExpired(account.ID);
                        drv.Quit();
                        drv = null;
                        retryCount++;
                    }
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"[Cookie] Алдаа (retry {retryCount}): " + ex.Message);
                    drv?.Quit();
                    drv = null;
                    retryCount++;
                }
            }

            throw new Exception("Бүх cookie account-аар нэвтрэж чадсангүй.");
        }

        // ════════════════════════════════════════════════════════
        // NavigateToProfile
        // ════════════════════════════════════════════════════════
        private void NavigateToProfile(IWebDriver drv, string fromId, string userName)
        {
            string url = !string.IsNullOrEmpty(fromId)
                ? "https://www.facebook.com/" + fromId
                : "https://www.facebook.com/" + userName;

            drv.Navigate().GoToUrl(url);
            Thread.Sleep(4000);

            if (!IsLoggedIn(drv))
            {
                Console.WriteLine("[Navigate] Session дууссан, дахин нэвтэрч байна...");
                var newAccount = GetNextCookieAccount();
                InjectCookies(drv, newAccount);
                drv.Navigate().GoToUrl("https://www.facebook.com/");
                Thread.Sleep(3000);

                if (!IsLoggedIn(drv))
                    throw new Exception("Session сэргээж чадсангүй.");

                drv.Navigate().GoToUrl(url);
                Thread.Sleep(4000);
            }
        }

        // ════════════════════════════════════════════════════════
        // UI HANDLERS
        // ════════════════════════════════════════════════════════
        private void btnStart_Click(object sender, EventArgs e)
        {
            LoadCookieAccounts();
            priorityHigh = Convert.ToInt32(txtPriorityHigh.Text);
            priorityMed  = Convert.ToInt32(txtPriorityMeduim.Text);
            priorityLow  = Convert.ToInt32(txtPriorityLow.Text);
            tmrLooper.Enabled = true;
            index = 0;
            makeQueue();
        }

        private void btnStop_Click(object sender, EventArgs e)
        {
            tmrLooper.Enabled = false;
        }

        private void makeQueue()
        {
            if (queue.Count == 0)
            {
                Facebook_AccTableAdapter = new Facebook_AccTableAdapter();
                Facebook_AccDataTable    = new DAL.MainDAL.Facebook_AccDataTable();
                Facebook_AccTableAdapter.Fill(Facebook_AccDataTable);
                foreach (DAL.MainDAL.Facebook_AccRow row in Facebook_AccDataTable.Rows)
                    queue.Add((row.ID, row.FbID, row.UserName));
            }
            else
            {
                queue.Clear();
            }
        }

        private async void tmrLooper_Tick(object sender, EventArgs e)
        {
            int freeChromeNodes = -1;
            try
            {
                freeChromeNodes = await gridStatusChecker.GetNumberOfFreeChromeNodesAsync();
                Console.WriteLine($"Number of free Chrome nodes: {freeChromeNodes}");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Error checking for free Chrome nodes: {ex.Message}");
            }
            try
            {
                if (session < 1)
                {
                    if (freeChromeNodes <= 0) return;

                    session++;
                    if (index >= queue.Count)
                    {
                        queue_indx++;
                        index = 0;
                        makeQueue();
                    }

                    Guid   id       = queue[index].Item1;
                    string FbID     = queue[index].Item2;
                    string UserName = queue[index].Item3;
                    ++index;

                    await postDownload(id, FbID, UserName);
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine("session");
                Console.WriteLine(ex.Message);
            }
        }

        // ════════════════════════════════════════════════════════
        // postDownload (НАЙЗЫН ТОО УНШИХ КОД НЭГТГЭСЭН ХЭСЭГ)
        // ════════════════════════════════════════════════════════
        async Task postDownload(Guid ID, string From_ID, string UserName)
        {
            IWebDriver drv = null;
            try
            {
                await Task.Run(() =>
                {
                    drv = chromeDriver();
                    string uniqueID      = null;
                    bool isLockedProfile = false;
                    Facebook_AccTableAdapter = new Facebook_AccTableAdapter();
                    Facebook_AccDataTable    = new DAL.MainDAL.Facebook_AccDataTable();
                    
                    // ХАНД ХАСАВ: UserName = null; мөрийг устгаж баазаас ирсэн нэрийг хадгаллаа.

                    try
                    {
                        // ── Login хийгдсэн driver-аар profile руу орно ──
                        NavigateToProfile(drv, From_ID, UserName);

                        new Actions(drv).SendKeys(OpenQA.Selenium.Keys.PageDown).Perform();
                        Thread.Sleep(5000);

                        string description = string.Empty;
                        IWebElement introHeader = drv.FindElement(By.XPath("//h2[.//span[text()='Intro']]"));
                        var sections = drv.FindElements(By.XPath("//h2"));
                        IWebElement introSection = null;

                        foreach (var section in sections)
                        {
                            string title = section.Text;
                            if (title.Contains("Intro") || title.Contains("About") || title.Contains("Танилцуулга"))
                            {
                                introSection = section;
                                break;
                            }
                        }

                        if (introSection != null)
                        {
                            var container = introSection.FindElement(By.XPath("./ancestor::div[5]"));
                            description = container.GetAttribute("innerText");
                            Console.WriteLine(description);
                        }
                        else
                        {
                            Console.WriteLine("Intro section not found");
                        }

                        try
                        {
                            IWebElement lockedProfile = drv.FindElement(By.CssSelector("div[role='heading']"));
                            string lockedText = lockedProfile.Text;
                            if (lockedText.Contains("locked") && lockedText.Contains("profile"))
                                isLockedProfile = true;
                        }
                        catch { }

                        string user_name = null;
                        string FbID = null;

                        if (!string.IsNullOrWhiteSpace(From_ID))
                        {
                            if (long.TryParse(From_ID, out long id)) FbID = From_ID;
                            else user_name = From_ID;
                        }

                        if (From_ID != null)
                            ID = (Guid)Facebook_AccTableAdapter.getIdByFbID(From_ID);
                        else
                            ID = (Guid)Facebook_AccTableAdapter.getIdByUserName(UserName);

                        if (From_ID == null)
                        {
                            try
                            {
                                try
                                {
                                    IReadOnlyCollection<IWebElement> scriptElements = drv.FindElements(By.XPath("//script"));
                                    foreach (IWebElement scriptElement in scriptElements)
                                    {
                                        IJavaScriptExecutor jsExecutor = (IJavaScriptExecutor)drv;
                                        string scriptData = (string)jsExecutor.ExecuteScript(
                                            "return arguments[0].textContent;", scriptElement);
                                        if (!string.IsNullOrEmpty(scriptData))
                                        {
                                            From_ID = ExtractIdFromJavaScript(scriptData);
                                            if (!string.IsNullOrEmpty(From_ID) && From_ID.Length >= 9) break;
                                        }
                                    }
                                    IReadOnlyCollection<IWebElement> scriptEl = drv.FindElements(By.XPath("//script"));
                                    if (string.IsNullOrEmpty(From_ID))
                                    {
                                        foreach (IWebElement scriptElement in scriptEl)
                                        {
                                            IJavaScriptExecutor jsExecutor = (IJavaScriptExecutor)drv;
                                            string scriptData = (string)jsExecutor.ExecuteScript(
                                                "return arguments[0].textContent;", scriptElement);
                                            if (!string.IsNullOrEmpty(scriptData))
                                            {
                                                From_ID = ExtractUserIdFromJavaScript(scriptData);
                                                if (!string.IsNullOrEmpty(From_ID) && From_ID.Length >= 9) break;
                                            }
                                        }
                                    }
                                }
                                catch (Exception ex)
                                {
                                    Console.WriteLine("Script read error:");
                                    Console.WriteLine(ex.Message);
                                }
                            }
                            catch { }
                        }

                        if (UserName == null)
                        {
                            try
                            {
                                try
                                {
                                    IReadOnlyCollection<IWebElement> scriptElements = drv.FindElements(By.XPath("//script"));
                                    foreach (IWebElement scriptElement in scriptElements)
                                    {
                                        IJavaScriptExecutor jsExecutor = (IJavaScriptExecutor)drv;
                                        string scriptData = (string)jsExecutor.ExecuteScript(
                                            "return arguments[0].textContent;", scriptElement);
                                        if (!string.IsNullOrEmpty(scriptData))
                                        {
                                            UserName = ExtractNameFromJavaScript(scriptData);
                                            if (!string.IsNullOrEmpty(UserName)) break;
                                        }
                                    }
                                }
                                catch (Exception ex)
                                {
                                    Console.WriteLine("Script read error:");
                                    Console.WriteLine(ex.Message);
                                }
                            }
                            catch { }
                        }

                        // ── Дагагч, Дагаж буй болон НАЙЗЫН ТООГ УНШИХ СИСТЕМ ──
                        int followers = 0;
                        int following = 0;
                        int friends = 0;

                        // Блок 1: Өөрийн тань бичсэн үндсэн хайлтын арга
                        try
                        {
                            IWebElement userNameElement = drv.FindElement(By.CssSelector("span[dir='auto']"));
                            string followersText = userNameElement.FindElement(By.CssSelector("a[href*='sk=followers']")).Text.Trim();
                            string followingText = userNameElement.FindElement(By.CssSelector("a[href*='sk=following'] strong")).Text.Trim();
                            followers = ConvertFacebookCountToInt(followersText);
                            following = ConvertFacebookCountToInt(followingText);
                        }
                        catch { }

                        // Блок 2: Тэжээлийн үндсэн div-ээс хайх (Fallback арга)
                        try
                        {
                            IWebElement statsElement = drv.FindElement(By.CssSelector("div[role='main']"));
                            
                            var followersEls = statsElement.FindElements(By.CssSelector("a[href*='followers'] strong"));
                            if (followersEls.Count > 0 && followers == 0)
                                followers = ConvertFacebookCountToInt(followersEls[0].Text.Trim());
                                
                            var followingEls = statsElement.FindElements(By.CssSelector("a[href*='following'] strong"));
                            if (followingEls.Count > 0 && following == 0)
                                following = ConvertFacebookCountToInt(followingEls[0].Text.Trim());

                            // ── ШИНЭ: Найзын тоог Regex болон Selector ашиглан авах ──
                            try
                            {
                                string mainHtml = statsElement.GetAttribute("outerHTML");
                                // Таны ирүүлсэн Regex-ийг C#-д тохируулан ажиллуулах
                                Match friendsMatch = Regex.Match(mainHtml, @"<strong[^>]*>([\d.,KkMmBb\s]+)<\/strong>\s*friends?", RegexOptions.IgnoreCase);
                                
                                if (friendsMatch.Success)
                                {
                                    string friendsText = friendsMatch.Groups[1].Value.Trim();
                                    friends = ConvertFacebookCountToInt(friendsText);
                                }
                                else
                                {
                                    // Хэрэв Regex тохирохгүй бол Friends линкний текстийг унших нөөц хувилбар
                                    var friendsEls = statsElement.FindElements(By.CssSelector("a[href*='sk=friends']"));
                                    foreach (var el in friendsEls)
                                    {
                                        string elText = el.Text.Trim();
                                        if (!string.IsNullOrEmpty(elText))
                                        {
                                            friends = ConvertFacebookCountToInt(elText);
                                            if (friends > 0) break;
                                        }
                                    }
                                }
                                Console.WriteLine($"[Scraping Үр дүн] Дагагч: {followers} | Дагаж буй: {following} | Найзууд: {friends}");
                            }
                            catch (Exception ex)
                            {
                                Console.WriteLine("Найзын тоо уншихад алдаа: " + ex.Message);
                            }
                        }
                        catch { }

                        // Эцсийн үр дүнг өгөгдлийн бааз руу шинэчилж хадгалах хэсэг (friends нэмэгдсэн)
                        try
                        {
                            Facebook_AccTableAdapter.UpdateAccountInfo(
                                followers, following, friends, description, DateTime.Now, From_ID, UserName, isLockedProfile, ID);
                        }
                        catch (Exception ex)
                        {
                            Console.WriteLine("UpdateAccountInfo SQL Алдаа: " + ex.Message);
                        }
                    }
                    catch { }
                });
            }
            catch (Exception Ex)
            {
                Console.WriteLine("task error");
                Console.WriteLine(Ex.Message);
            }
            finally
            {
                if (session > 0) session--;
                drv?.Quit();
            }
        }

        // ════════════════════════════════════════════════════════
        // HELPER МЕТОДУУД (өөрчлөгдөөгүй)
        // ════════════════════════════════════════════════════════
        public string ExtractNameFromJavaScript(string scriptData)
        {
            string setname = null;
            try
            {
                if (string.IsNullOrWhiteSpace(scriptData)) return null;
                scriptData = scriptData.Replace("\\/", "/");
                scriptData = scriptData.Replace("\\\"", "\"");
                Match nameMatch = Regex.Match(
                    scriptData,
                    @"""userVanity""\s*:\s*""(?<name>[^""]*)""",
                    RegexOptions.Singleline);
                if (nameMatch.Success) setname = nameMatch.Groups["name"].Value;
            }
            catch (Exception ex)
            {
                Console.WriteLine("ExtractNameFromJavaScript error:");
                Console.WriteLine(ex.Message);
            }
            return setname;
        }

        private string NormalizeFacebookScript(string scriptData)
        {
            if (string.IsNullOrWhiteSpace(scriptData)) return null;
            return scriptData.Replace("\\/", "/").Replace("\\\"", "\"");
        }

        public string ExtractUserIdFromJavaScript(string scriptData)
        {
            try
            {
                Thread.Sleep(10000);
                scriptData = NormalizeFacebookScript(scriptData);
                if (string.IsNullOrEmpty(scriptData)) return null;
                Match userIdMatch = Regex.Match(
                    scriptData,
                    @"""userID""\s*:\s*""(?<id>\d{10,})""",
                    RegexOptions.Singleline);
                if (userIdMatch.Success) return userIdMatch.Groups["id"].Value;
            }
            catch (Exception ex)
            {
                Console.WriteLine("ExtractUserIdFromJavaScript error:");
                Console.WriteLine(ex.Message);
            }
            return null;
        }

        public string ExtractIdFromJavaScript(string scriptData)
        {
            string setid = null;
            try
            {
                if (string.IsNullOrWhiteSpace(scriptData)) return null;
                scriptData = scriptData.Replace("\\/", "/");
                if (!scriptData.Contains("\"actors\"")) return null;

                string actorPattern = @"""actors""\s*:\s*\[\s*\{(?<actor>[^}]*)\}";
                MatchCollection actorMatches = Regex.Matches(scriptData, actorPattern, RegexOptions.Singleline);

                foreach (Match actorMatch in actorMatches)
                {
                    string actorText = actorMatch.Groups["actor"].Value;
                    Match idMatch  = Regex.Match(actorText, @"""id""\s*:\s*""(?<id>\d+)""");
                    Match urlMatch = Regex.Match(actorText, @"""url""\s*:\s*""(?<url>https?://[^""]+)""");
                    if (!idMatch.Success) continue;
                    setid = idMatch.Groups["id"].Value;
                    string groupUrl = urlMatch.Success ? urlMatch.Groups["url"].Value.TrimEnd('/') : "";
                    if (!string.IsNullOrEmpty(setid) && setid.Length > 9) break;
                    Console.WriteLine("URL: " + groupUrl);
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine("ExtractPageIdFromJavaScript error:");
                Console.WriteLine(ex.Message);
            }
            return setid;
        }

        static int ConvertFacebookCountToInt(string value)
        {
            if (string.IsNullOrWhiteSpace(value)) return 0;
            // Зөвхөн арын friends эсвэл хоосон зайг цэвэрлэх уян хатан шүүлтүүр
            value = value.Trim().Replace(",", "").Replace(" ", "");
            Match match = Regex.Match(value, @"([\d.]+)([KMB]?)$", RegexOptions.IgnoreCase);
            if (!match.Success) return 0;
            if (!double.TryParse(match.Groups[1].Value, NumberStyles.Any, CultureInfo.InvariantCulture, out double number))
                return 0;
            string suffix = match.Groups[2].Value.ToUpperInvariant();
            double multiplier = suffix == "K" ? 1000 : suffix == "M" ? 1000000 : suffix == "B" ? 1000000000 : 1;
            return (int)(number * multiplier);
        }

        private void exportComment(Guid ID, IWebDriver drv)
        {
            IWebElement commentArticle;
            IWebElement detailInfo;
            ReadOnlyCollection<IWebElement> detailInfos;
            ReadOnlyCollection<IWebElement> comments;
            int commentReactionCount = 0;

            new Actions(drv).SendKeys(OpenQA.Selenium.Keys.PageDown).Perform();
            Task.Delay(100000);
            comments = drv.FindElements(By.CssSelector("div[aria-label*='Comment by'][role= article]"));
            IJavaScriptExecutor js_scroll = (IJavaScriptExecutor)drv;
            new Actions(drv).SendKeys(OpenQA.Selenium.Keys.PageDown).Perform();
            Task.Delay(50000);
            comments = drv.FindElements(By.CssSelector("div[aria-label*='Comment by'][role= article]"));

            for (int k = 0; k < comments.Count; k++)
            {
                try
                {
                    commentArticle = comments[k];
                    try { detailInfo = commentArticle.FindElement(By.CssSelector("a[aria-hidden='false'][role='link']")); }
                    catch { detailInfo = commentArticle.FindElement(By.CssSelector("div[aria-hidden='false'][role='button']")); }

                    try { detailInfos = commentArticle.FindElements(By.CssSelector("a[role='link']")); }
                    catch { }

                    detailInfos = commentArticle.FindElements(By.CssSelector("a[role='link']"));
                    string userUrl      = detailInfo.GetAttribute("href");
                    string userName     = commentArticle.FindElement(By.TagName("span")).Text;
                    string commenterUrl = detailInfos[0].GetAttribute("href");
                    string commentUrl   = detailInfos[0].GetAttribute("href");
                    IWebElement commentEl = commentArticle.FindElement(By.CssSelector("div[dir='auto'][style*='text-align']"));
                    string commentText  = commentEl.Text;
                    string dateStrs     = commentArticle.FindElement(By.TagName("span")).Text;
                    if (dateStrs == "") dateStrs = detailInfos[0].Text;
                    DateTime commentdateTime = GetDateTimeFromString(dateStrs);
                    if (dateStrs == "") commentdateTime = DateTime.Now;

                    ((IJavaScriptExecutor)drv).ExecuteScript("arguments[0].scrollIntoView(true);", commentEl);
                    ((IJavaScriptExecutor)drv).ExecuteScript("window.scrollBy(0, -100);");

                    Uri uri = new Uri(commentUrl);
                    var queryParams = HttpUtility.ParseQueryString(uri.Query);
                    string commentId = queryParams["comment_id"];
                    string commenterFromID = FindCommentFromID(commentUrl);

                    string commentArticleHtml = commentArticle.GetAttribute("outerHTML");
                    HtmlAgilityPack.HtmlDocument document = new HtmlAgilityPack.HtmlDocument();
                    document.LoadHtml(commentArticleHtml);
                    var imageNode = document.DocumentNode.SelectSingleNode("//image");
                    string finalUrl = null;
                    if (imageNode != null)
                    {
                        string rawUrl = imageNode.GetAttributeValue("xlink:href", string.Empty);
                        if (!string.IsNullOrEmpty(rawUrl))
                        {
                            finalUrl = WebUtility.HtmlDecode(rawUrl);
                            Console.WriteLine($"Final Image URL: {finalUrl}");
                        }
                        else Console.WriteLine("Image URL attribute is empty or not found.");
                    }
                    else Console.WriteLine("Image node not found.");

                    if (userName == "")
                    {
                        Task.Delay(3000);
                        userName = commentArticle
                            .FindElement(By.XPath(".//span[@dir='auto' and not(@lang)][1]")).Text.Trim();
                        commentText = commentArticle
                            .FindElement(By.XPath(".//span[@dir='auto' and @lang]//div[@dir='auto'][contains(@style,'text-align')][1]"))
                            .Text.Trim();
                    }
                    if (k == 0 && userName == "") exportComment(ID, drv);
                }
                catch (Exception ex) { }
                finally { }
            }
        }

        public string Between(string STR, string FirstString, string LastString)
        {
            int Pos1 = STR.IndexOf(FirstString) + FirstString.Length;
            int Pos2 = STR.IndexOf(LastString);
            return STR.Substring(Pos1, Pos2 - Pos1);
        }

        private string GetFacebookUrl2days(string param, string type)
        {
            string result = "";
            switch (type)
            {
                case "posts":  wbBrwsr.Document.GetElementById("select_search_type").SetAttribute("value", "posts"); break;
                case "videos": wbBrwsr.Document.GetElementById("select_search_type").SetAttribute("value", "videos"); break;
            }
            wbBrwsr.Document.GetElementById("select_search_type").RaiseEvent("onChange");
            wbBrwsr.Document.GetElementsByTagName("input").GetElementsByName("clear-filters")[0].InvokeMember("Click");
            string year  = DateTime.Now.Year.ToString();
            string month = DateTime.Now.Month.ToString();
            int intDay   = DateTime.Now.Date.Day;
            string day   = intDay.ToString();
            string preDay = (intDay - 1 != 0) ? (intDay - 1).ToString() : day;
            wbBrwsr.Document.GetElementById("start_year").SetAttribute("value", year);
            wbBrwsr.Document.GetElementById("end_year").SetAttribute("value", year);
            wbBrwsr.Document.GetElementById("start_month").SetAttribute("value", month);
            wbBrwsr.Document.GetElementById("end_month").SetAttribute("value", month);
            wbBrwsr.Document.GetElementById("start_day").SetAttribute("value", preDay);
            wbBrwsr.Document.GetElementById("end_day").SetAttribute("value", day);
            wbBrwsr.Document.GetElementById("date-filter").InvokeMember("Click");
            wbBrwsr.Document.GetElementById("search_keyword").SetAttribute("value", param);
            wbBrwsr.Document.GetElementById("btn_make_url").InvokeMember("Click");
            return wbBrwsr.Document.GetElementById("txt_result").GetAttribute("value").ToString();
        }

        private string GetFacebookUrl7days(string param, string type)
        {
            string result = "";
            switch (type)
            {
                case "posts":  wbBrwsr.Document.GetElementById("select_search_type").SetAttribute("value", "posts"); break;
                case "videos": wbBrwsr.Document.GetElementById("select_search_type").SetAttribute("value", "videos"); break;
            }
            wbBrwsr.Document.GetElementById("select_search_type").RaiseEvent("onChange");
            wbBrwsr.Document.GetElementsByTagName("input").GetElementsByName("clear-filters")[0].InvokeMember("Click");
            string year  = DateTime.Now.Year.ToString();
            string month = DateTime.Now.Month.ToString();
            int intDay   = DateTime.Now.Date.Day;
            string day   = intDay.ToString();
            string preDay = (intDay - 1 != 0) ? (intDay - 7).ToString() : day;
            wbBrwsr.Document.GetElementById("start_year").SetAttribute("value", year);
            wbBrwsr.Document.GetElementById("end_year").SetAttribute("value", year);
            wbBrwsr.Document.GetElementById("start_month").SetAttribute("value", month);
            wbBrwsr.Document.GetElementById("end_month").SetAttribute("value", month);
            wbBrwsr.Document.GetElementById("start_day").SetAttribute("value", preDay);
            wbBrwsr.Document.GetElementById("end_day").SetAttribute("value", day);
            wbBrwsr.Document.GetElementById("date-filter").InvokeMember("Click");
            wbBrwsr.Document.GetElementById("search_keyword").SetAttribute("value", param);
            wbBrwsr.Document.GetElementById("btn_make_url").InvokeMember("Click");
            return wbBrwsr.Document.GetElementById("txt_result").GetAttribute("value").ToString();
        }

        private DateTime GetDateTimeFromString(string dateStr)
        {
            DateTime result    = DateTime.Now;
            DateTime startDate = DateTime.Now;
            dateStr = dateStr.Replace('\u202F', ' ');

            if (DateTime.TryParseExact(dateStr, "MMMM d",           CultureInfo.InvariantCulture, DateTimeStyles.None, out result)) return result;
            if (DateTime.TryParseExact(dateStr, "MMMM dd, yyyy",    CultureInfo.InvariantCulture, DateTimeStyles.None, out result)) return result;
            if (DateTime.TryParseExact(dateStr, "MMMM d, yyyy",     CultureInfo.InvariantCulture, DateTimeStyles.None, out result)) return result;
            if (DateTime.TryParseExact(dateStr, "dddd, MMMM dd, yyyy 'at' hh:mm tt", CultureInfo.InvariantCulture, DateTimeStyles.None, out result)) return result;
            if (DateTime.TryParseExact(dateStr, "dddd, MMMM d, yyyy 'at' h:mm tt",   CultureInfo.InvariantCulture, DateTimeStyles.None, out result)) return result;

            if (dateStr.Contains("about an hour ago")) return startDate.AddHours(-1);

            if (dateStr.Contains("hr") || dateStr.Contains("hour") || dateStr.Contains("hours") || dateStr.EndsWith("h"))
            {
                string n = new string(dateStr.Where(char.IsDigit).ToArray());
                if (int.TryParse(n, out int hours)) return startDate.AddHours(-hours);
            }
            if (dateStr.Contains("days ago"))
            {
                int daysAgo = 0;
                if (dateStr.Contains("a ")) daysAgo = 1;
                else { string n = new string(dateStr.TakeWhile(char.IsDigit).ToArray()); int.TryParse(n, out daysAgo); }
                return startDate.AddDays(-daysAgo);
            }
            if (dateStr.Contains("day ago")) return startDate.AddDays(-1);
            if (dateStr.Equals("a few seconds ago", StringComparison.OrdinalIgnoreCase)) return DateTime.Now;
            if (DateTime.TryParseExact(dateStr, "MMMM d 'at' h:mm tt", CultureInfo.InvariantCulture, DateTimeStyles.None, out result)) return result;
            if (dateStr.Contains("minutes ago") || dateStr.EndsWith("m") || dateStr.Contains("min") || dateStr.Contains("mins"))
            {
                string n = new string(dateStr.Where(char.IsDigit).ToArray());
                if (int.TryParse(n, out int minutes)) return startDate.AddMinutes(-minutes);
            }
            if (dateStr.EndsWith("d"))
            {
                string n = new string(dateStr.TakeWhile(char.IsDigit).ToArray());
                if (int.TryParse(n, out int dday)) return startDate.AddDays(-dday);
            }
            if (DateTime.TryParseExact(dateStr, "MMMM dd, yyyy 'at' h:mm tt", CultureInfo.InvariantCulture, DateTimeStyles.None, out result))
            {
                TimeSpan diff = DateTime.Now - result;
                return DateTime.Now.Add(-diff);
            }
            return result;
        }

        private string FindCommentFromID(string postUrl)
        {
            string fromID = null;
            string fromUrl = null;
            string FromUserName = null;
            if (postUrl.Contains("profile.php?"))
            {
                Uri myUri = new Uri(postUrl);
                fromID = HttpUtility.ParseQueryString(myUri.Query).Get("id");
                int endIndex = postUrl.IndexOf("&");
                fromUrl = endIndex != -1 ? postUrl.Substring(0, endIndex) : postUrl;
            }
            else
            {
                int indexUrl = postUrl.IndexOf("facebook.com/");
                if (postUrl.Contains("groups"))
                {
                    if (indexUrl != -1)
                    {
                        string substring = postUrl.Substring(indexUrl + "facebook.com/groups/".Length);
                        int endIndex = substring.IndexOf("/?");
                        FromUserName = endIndex != -1 ? substring.Substring(0, endIndex) : substring;
                        int end_Indx = postUrl.IndexOf("/?");
                        fromUrl = end_Indx != -1 ? postUrl.Substring(0, end_Indx) : postUrl;
                    }
                }
                else
                {
                    if (indexUrl != -1)
                    {
                        string substring = postUrl.Substring(indexUrl + "facebook.com/".Length);
                        int endIndex = substring.IndexOf("?");
                        FromUserName = endIndex != -1 ? substring.Substring(0, endIndex) : substring;
                        int end_Indx = postUrl.IndexOf("?");
                        fromUrl = end_Indx != -1 ? postUrl.Substring(0, end_Indx) : postUrl;
                    }
                }
            }
            return fromID;
        }

        private void FrmMain_Load(object sender, EventArgs e)
        {
            wbBrwsr.Navigate(Directory.GetCurrentDirectory() + "/fbsearch.html");
        }

        private void chbLast2Days_CheckedChanged(object sender, EventArgs e)
        {
            if (chbLast2Days.Checked)
                searchURL = GetFacebookUrl2days("testerSearcherParam", "posts");
        }

        private void chbLast7Days_CheckedChanged(object sender, EventArgs e)
        {
            if (chbWithin1Week.Checked)
                searchURL = GetFacebookUrl7days("testerSearcherParam", "posts");
        }

        private void wbBrwsr_DocumentCompleted(object sender, WebBrowserDocumentCompletedEventArgs e) { }

        private void txtClientID_TextChanged(object sender, EventArgs e) { }
    }
}