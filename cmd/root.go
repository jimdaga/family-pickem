package cmd

import (
	"fmt"
	"os"

	"github.com/spf13/cobra"
	"github.com/spf13/viper"

	"github.com/jimdaga/pickemcli/pkg/daemon"
	"github.com/jimdaga/pickemcli/pkg/userStats"
)

var Debug bool

var rootCmd = &cobra.Command{
	Use:   "pickemcli",
	Short: "pickemcli is a cli tool for updating the family-pickem.com website",
	Long:  "pickemcli is a cli tool for updating analytic data and score data for the family-pickem.com website",
	Run: func(cmd *cobra.Command, args []string) {

	},
}

func Execute() {
	if err := rootCmd.Execute(); err != nil {
		fmt.Fprintf(os.Stderr, "Oops. An error while executing pickemcli '%s'\n", err)
		os.Exit(1)
	}
}

func addSubcommandPallets() {
	// Add the main userStats command that runs all analytics
	rootCmd.AddCommand(userStats.UserStats)

	// Add individual analytics commands for backwards compatibility
	rootCmd.AddCommand(userStats.PickStats)
	rootCmd.AddCommand(userStats.TopPicked)
	rootCmd.AddCommand(userStats.LeastPicked)

	// Add daemon command
	rootCmd.AddCommand(daemon.DaemonCmd)
}

func init() {

	rootCmd.Root().CompletionOptions.DisableDefaultCmd = true

	rootCmd.SetHelpCommand(&cobra.Command{
		Use:    "no-help",
		Hidden: true,
	})

	rootCmd.PersistentFlags().BoolVarP(&Debug, "debug", "d", false, "Display debugging output in the console. (default: false)")
	if err := viper.BindPFlag("debug", rootCmd.PersistentFlags().Lookup("debug")); err != nil {
		panic(err.Error())
	}

	addSubcommandPallets()

	// Load configuration
	viper.AddConfigPath(".")
	viper.SetConfigName("config")
	viper.SetConfigType("yaml")

	if err := viper.ReadInConfig(); err != nil {
		if _, ok := err.(viper.ConfigFileNotFoundError); !ok {
			panic(fmt.Errorf("fatal error reading config file: %w", err))
		}
	}

	// Set Defaults
	viper.SetDefault("daemon.interval", 30)
	viper.SetDefault("app.season.current", "2425")

}
