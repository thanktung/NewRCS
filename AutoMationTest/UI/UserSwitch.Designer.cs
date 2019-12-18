namespace AutoMationTest.UI
{
    partial class UserSwitch
    {
        /// <summary> 
        /// 設計工具所需的變數。
        /// </summary>
        private System.ComponentModel.IContainer components = null;

        /// <summary> 
        /// 清除任何使用中的資源。
        /// </summary>
        /// <param name="disposing">如果應該處置 Managed 資源則為 true，否則為 false。</param>
        protected override void Dispose(bool disposing)
        {
            if (disposing && (components != null))
            {
                components.Dispose();
            }
            base.Dispose(disposing);
        }

        #region 元件設計工具產生的程式碼

        /// <summary> 
        /// 此為設計工具支援所需的方法 - 請勿使用程式碼編輯器
        /// 修改這個方法的內容。
        /// </summary>
        private void InitializeComponent()
        {
            this.SuspendLayout();
            // 
            // UserSwitch
            // 
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.None;
            this.Cursor = System.Windows.Forms.Cursors.Hand;
            this.Font = new System.Drawing.Font("Calibri", 12F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(0)));
            this.Margin = new System.Windows.Forms.Padding(4, 5, 4, 5);
            this.Name = "UserSwitch";
            this.Size = new System.Drawing.Size(60, 60);
            this.Load += new System.EventHandler(this.UserSwitch_Load);
            this.Click += new System.EventHandler(this.UserSwitch_Click);
            this.Paint += new System.Windows.Forms.PaintEventHandler(this.UserSwitch_Paint);
            this.ResumeLayout(false);

        }

        #endregion
    }
}
