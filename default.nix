{ nixpkgs ? (import <nixpkgs> {}) }:

with nixpkgs;
let
  hackage-cli =
    let src = fetchFromGitHub {
        owner = "hackage-trustees";
        repo = "hackage-cli";
        rev = "d50463879a5ffbcc8d7d10811e8479cb9e6943e5";
        sha256 = "1cclhlaih7bx0lis6h60v8s1ydzdakh037dni7z1falg75yzvrlv";
      };
    in haskellPackages.callCabal2nix "hackage-cli" src {
      netrc = haskell.lib.dontCheck haskellPackages.netrc;
      Cabal = haskellPackages.Cabal_3_0_0_0;
    };

  haskellPackages = haskell.packages.ghc865;

  scripts = python3Packages.buildPythonPackage {
    pname = "hs-maintainer-tools";
    version = "1.0";
    src = ./.;
    preBuild = ''
      mypy cabal_bump.py
    '';
    nativeBuildInputs = [ mypy ];
    propagatedBuildInputs = [
      git curl nix
      cabal-install
      haskellPackages.haddock
      hackage-cli
    ] ++ (with python3Packages; [
      termcolor
    ]);
  };
in scripts
