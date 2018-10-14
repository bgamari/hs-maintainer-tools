let
  nixpkgs = import <nixpkgs> {};
in with nixpkgs;
let
  prefixPaths = prog: outName: pkgs: ''
    cp ${prog} $out/bin/${outName}
    wrapProgram $out/bin/${outName} ''
    + lib.concatMapStringsSep " " (pkg: "--prefix PATH : ${pkg}/bin") pkgs;

  scripts = stdenv.mkDerivation {
    name = "hs-maintainer-tools";
    src = ./.;
    nativeBuildInputs = [ makeWrapper ];
    installPhase = ''
      mkdir -p $out/bin
      ${prefixPaths ./cabal-bump.py "cabal-bump" [ git curl cabal-install haskellPackages.haddock nix python3 ]}
    '';
  };
in scripts
