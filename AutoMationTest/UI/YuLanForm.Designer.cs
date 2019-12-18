namespace AutoMationTest.UI
{
    partial class YuLanForm
    {
        /// <summary> 
        /// 必需的设计器变量。
        /// </summary>
        private System.ComponentModel.IContainer components = null;

        /// <summary> 
        /// 清理所有正在使用的资源。
        /// </summary>
        /// <param name="disposing">如果应释放托管资源，为 true；否则为 false。</param>
        protected override void Dispose(bool disposing)
        {
            if (disposing && (components != null))
            {
                components.Dispose();
            }
            base.Dispose(disposing);
        }

        #region 组件设计器生成的代码

        /// <summary> 
        /// 设计器支持所需的方法 - 不要
        /// 使用代码编辑器修改此方法的内容。
        /// </summary>
        private void InitializeComponent()
        {
            this.components = new System.ComponentModel.Container();
            System.ComponentModel.ComponentResourceManager resources = new System.ComponentModel.ComponentResourceManager(typeof(YuLanForm));
            this.YulanMenu = new System.Windows.Forms.ContextMenuStrip(this.components);
            this.隱藏ToolStripMenuItem = new System.Windows.Forms.ToolStripMenuItem();
            this.測試標準件ToolStripMenuItem = new System.Windows.Forms.ToolStripMenuItem();
            this.詳細信息ToolStripMenuItem = new System.Windows.Forms.ToolStripMenuItem();
            this.autoPanel1 = new AutoMationTest.UI.AutoPanel();
            this.YulanMenu.SuspendLayout();
            this.SuspendLayout();
            // 
            // YulanMenu
            // 
            this.YulanMenu.Items.AddRange(new System.Windows.Forms.ToolStripItem[] {
            this.隱藏ToolStripMenuItem,
            this.測試標準件ToolStripMenuItem,
            this.詳細信息ToolStripMenuItem});
            this.YulanMenu.Name = "YulanMenu";
            this.YulanMenu.Size = new System.Drawing.Size(135, 70);
            this.YulanMenu.Opening += new System.ComponentModel.CancelEventHandler(this.YulanMenu_Opening);
            // 
            // 隱藏ToolStripMenuItem
            // 
            this.隱藏ToolStripMenuItem.Image = ((System.Drawing.Image)(resources.GetObject("隱藏ToolStripMenuItem.Image")));
            this.隱藏ToolStripMenuItem.Name = "隱藏ToolStripMenuItem";
            this.隱藏ToolStripMenuItem.Size = new System.Drawing.Size(134, 22);
            this.隱藏ToolStripMenuItem.Text = "隱藏";
            this.隱藏ToolStripMenuItem.Click += new System.EventHandler(this.隱藏ToolStripMenuItem_Click);
            // 
            // 測試標準件ToolStripMenuItem
            // 
            this.測試標準件ToolStripMenuItem.Image = ((System.Drawing.Image)(resources.GetObject("測試標準件ToolStripMenuItem.Image")));
            this.測試標準件ToolStripMenuItem.Name = "測試標準件ToolStripMenuItem";
            this.測試標準件ToolStripMenuItem.Size = new System.Drawing.Size(134, 22);
            this.測試標準件ToolStripMenuItem.Text = "測試標準件";
            this.測試標準件ToolStripMenuItem.Click += new System.EventHandler(this.測試標準件ToolStripMenuItem_Click);
            // 
            // 詳細信息ToolStripMenuItem
            // 
            this.詳細信息ToolStripMenuItem.Image = ((System.Drawing.Image)(resources.GetObject("詳細信息ToolStripMenuItem.Image")));
            this.詳細信息ToolStripMenuItem.Name = "詳細信息ToolStripMenuItem";
            this.詳細信息ToolStripMenuItem.Size = new System.Drawing.Size(134, 22);
            this.詳細信息ToolStripMenuItem.Text = "詳細信息";
            // 
            // autoPanel1
            // 
            this.autoPanel1.AutoScroll = true;
            this.autoPanel1.Dock = System.Windows.Forms.DockStyle.Fill;
            this.autoPanel1.Location = new System.Drawing.Point(0, 0);
            this.autoPanel1.Name = "autoPanel1";
            this.autoPanel1.Size = new System.Drawing.Size(168, 350);
            this.autoPanel1.TabIndex = 0;
            // 
            // YuLanForm
            // 
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.None;
            this.Controls.Add(this.autoPanel1);
            this.Name = "YuLanForm";
            this.Size = new System.Drawing.Size(168, 350);
            this.Load += new System.EventHandler(this.YuLan_Load);
            this.YulanMenu.ResumeLayout(false);
            this.ResumeLayout(false);

        }

        #endregion

        private AutoPanel autoPanel1;
        private System.Windows.Forms.ContextMenuStrip YulanMenu;
        private System.Windows.Forms.ToolStripMenuItem 隱藏ToolStripMenuItem;
        private System.Windows.Forms.ToolStripMenuItem 測試標準件ToolStripMenuItem;
        private System.Windows.Forms.ToolStripMenuItem 詳細信息ToolStripMenuItem;
    }
}
