using System;
using System.Collections.Generic;
using System.Linq;
using System.Windows.Forms;

namespace RobotMainForm
{
    static class Program
    {

        public static MainForm mainform = new MainForm();

        /// <summary>
        /// 应用程序的主入口点。
        /// </summary>
        [STAThread]
        static void Main()
        {
            try
            {
                Application.EnableVisualStyles();
                //Application.SetCompatibleTextRenderingDefault(false);
                Application.Run(mainform);
            }
            catch (Exception ex)
            {
                MessageBox.Show(ex.ToString());
            }
        }
    }
}
